"""Postgres helpers for the Genesis engine.

Active only when DATABASE_URL is set (Railway Postgres plugin provides it).
Everything here fails soft: callers fall back to files when Postgres is
absent or unreachable. No import-time connections, no global state beyond
a cached availability probe.

Tables (created with IF NOT EXISTS, never migrated destructively):
  genesis_kv          — general key/value docs (gate store, usage, flags)
  genesis_hits        — rate-limit timestamps (shared across workers)
  genesis_experience  — memory lessons (append + filtered read + verify)
"""

from __future__ import annotations

import json
import os
import time

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS genesis_kv"
    " (k TEXT PRIMARY KEY, v JSONB NOT NULL)",
    "CREATE TABLE IF NOT EXISTS genesis_hits"
    " (ip TEXT NOT NULL, ts DOUBLE PRECISION NOT NULL)",
    "CREATE INDEX IF NOT EXISTS genesis_hits_ts_idx ON genesis_hits (ts)",
    "CREATE TABLE IF NOT EXISTS genesis_experience"
    " (id TEXT PRIMARY KEY, time TEXT NOT NULL, kind TEXT NOT NULL,"
    "  project TEXT NOT NULL, payload JSONB NOT NULL, verified BOOLEAN NOT NULL)",
    "CREATE INDEX IF NOT EXISTS genesis_exp_kind_idx"
    " ON genesis_experience (kind, project, verified)",
)

_prob_cache: tuple[float, bool] = (0.0, False)


def db_url() -> str:
    """DATABASE_URL when it looks like Postgres, else ''."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith(("postgresql://", "postgres://")):
        return url
    return ""


def connect():
    """A new psycopg2 connection, or None (no URL / no driver). Never raises."""
    url = db_url()
    if not url:
        return None
    try:
        import psycopg2
    except ImportError:
        return None
    try:
        return psycopg2.connect(url, connect_timeout=5)
    except Exception:
        return None


def ensure_schema(conn) -> bool:
    """CREATE TABLE IF NOT EXISTS for every engine table. Never raises."""
    try:
        cur = conn.cursor()
        try:
            for stmt in SCHEMA:
                cur.execute(stmt)
            conn.commit()
        finally:
            cur.close()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def available() -> bool:
    """True when Postgres answers SELECT 1 (result cached 60s). Never raises."""
    global _prob_cache
    now = time.time()
    if now - _prob_cache[0] < 60:
        return _prob_cache[1]
    ok = False
    con = connect()
    if con is not None:
        try:
            cur = con.cursor()
            try:
                cur.execute("SELECT 1")
                cur.fetchone()
                ok = True
            finally:
                cur.close()
        except Exception:
            ok = False
        finally:
            try:
                con.close()
            except Exception:
                pass
    _prob_cache = (now, ok)
    return ok


def kv_get(conn, key: str):
    cur = conn.cursor()
    try:
        cur.execute("SELECT v FROM genesis_kv WHERE k = %s", (key,))
        row = cur.fetchone()
    finally:
        cur.close()
    if not row:
        return None
    v = row[0]
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return v
    return v


def kv_set(conn, key: str, value) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO genesis_kv (k, v) VALUES (%s, %s)"
            " ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v",
            (key, json.dumps(value)),
        )
        conn.commit()
    finally:
        cur.close()


def hit(conn, ip: str, now: float) -> None:
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO genesis_hits (ip, ts) VALUES (%s, %s)", (ip, now))
        conn.commit()
    finally:
        cur.close()


def count_recent(conn, ip: str, since: float) -> int:
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM genesis_hits WHERE ip = %s AND ts >= %s",
                    (ip, since))
        row = cur.fetchone()
    finally:
        cur.close()
    return int(row[0]) if row else 0


def prune_hits(conn, cutoff: float) -> None:
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM genesis_hits WHERE ts < %s", (cutoff,))
        conn.commit()
    finally:
        cur.close()


def exp_insert(conn, exp: dict) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO genesis_experience (id, time, kind, project, payload, verified)"
            " VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (exp["id"], exp["time"], exp["kind"], exp["project"],
             json.dumps(exp.get("payload") or {}), bool(exp.get("verified"))),
        )
        conn.commit()
    finally:
        cur.close()


def exp_query(conn, kind=None, project=None, verified_only: bool = False,
              limit: int = 500) -> list[dict]:
    where = []
    args: list = []
    if kind:
        where.append("kind = %s")
        args.append(kind)
    if project:
        where.append("project = %s")
        args.append(project)
    if verified_only:
        where.append("verified = TRUE")
    sql = ("SELECT id, time, kind, project, payload, verified"
           " FROM genesis_experience")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY time DESC LIMIT %s"
    args.append(max(1, min(limit, 5000)))
    cur = conn.cursor()
    try:
        cur.execute(sql, tuple(args))
        rows = cur.fetchall()
    finally:
        cur.close()
    out = []
    for r in rows:
        payload = r[4]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except ValueError:
                payload = {}
        out.append({"id": r[0], "time": r[1], "kind": r[2],
                    "project": r[3], "payload": payload or {},
                    "verified": bool(r[5])})
    return out


def exp_confirm(conn, experience_id: str) -> bool:
    """Flip verified=True. Matches file-store semantics exactly:
    KeyError when missing, ValueError when already verified."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT verified FROM genesis_experience WHERE id = %s",
                    (experience_id,))
        row = cur.fetchone()
        if not row:
            raise KeyError(experience_id)
        if row[0]:
            raise ValueError("already verified")
        cur.execute("UPDATE genesis_experience SET verified = TRUE WHERE id = %s",
                    (experience_id,))
        conn.commit()
        return True
    finally:
        cur.close()
