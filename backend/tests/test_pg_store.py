"""Postgres engine store (M2): SQL shapes, fallback logic, live probe.

All logic tests run against a fake connection (no server needed).
The live test only runs when DATABASE_URL points at a real Postgres.
"""

import json
import os

import pytest

from app.db import pg


class FakeCursor:
    def __init__(self, fetchone=None, fetchall=None, fail_on=None):
        self.statements = []
        self._one = fetchone
        self._all = fetchall or []
        self._fail_on = fail_on or ()
        self.closed = False

    def execute(self, sql, params=None):
        self.statements.append((sql, params))
        for marker in self._fail_on:
            if marker in sql:
                raise RuntimeError("boom: " + marker)

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all

    def close(self):
        self.closed = True


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_db_url_accepts_only_postgres(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    assert pg.db_url().startswith("postgresql://")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///x.db")
    assert pg.db_url() == ""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert pg.db_url() == ""


def test_connect_none_without_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert pg.connect() is None


def test_ensure_schema_runs_all_tables():
    cur = FakeCursor()
    con = FakeConn(cur)
    assert pg.ensure_schema(con) is True
    assert con.commits == 1
    joined = " ".join(s for s, _ in cur.statements)
    assert "genesis_kv" in joined
    assert "genesis_hits" in joined
    assert "genesis_experience" in joined


def test_ensure_schema_failure_rolls_back():
    cur = FakeCursor(fail_on=("genesis_hits",))
    con = FakeConn(cur)
    assert pg.ensure_schema(con) is False
    assert con.rollbacks == 1


def test_kv_roundtrip_shape():
    cur = FakeCursor(fetchone=("{\"a\": 1}",))
    con = FakeConn(cur)
    assert pg.kv_get(con, "k1") == {"a": 1}
    assert cur.statements[0][0].startswith("SELECT v FROM genesis_kv")
    pg.kv_set(con, "k1", {"a": 1})
    sql, params = cur.statements[-1]
    assert "ON CONFLICT (k) DO UPDATE" in sql
    assert json.loads(params[1]) == {"a": 1}
    assert con.commits == 1


def test_kv_get_missing_is_none():
    cur = FakeCursor(fetchone=None)
    assert pg.kv_get(FakeConn(cur), "nope") is None


def test_hits_flow():
    cur = FakeCursor(fetchone=(7,))
    con = FakeConn(cur)
    pg.hit(con, "1.2.3.4", 100.0)
    assert pg.count_recent(con, "1.2.3.4", 40.0) == 7
    pg.prune_hits(con, 40.0)
    kinds = [s.split()[0] for s, _ in cur.statements]
    assert kinds == ["INSERT", "SELECT", "DELETE"]
    assert con.commits == 2  # hit + prune (count is read-only)


def test_exp_insert_query_mapping():
    cur = FakeCursor(fetchall=[
        ("exp-1", "2026-01-01T00:00:00+00:00", "decision", "p1",
         "{\"x\": 1}", True),
    ])
    con = FakeConn(cur)
    rows = pg.exp_query(con, kind="decision", project="p1", verified_only=True)
    assert rows[0]["payload"] == {"x": 1}
    assert rows[0]["verified"] is True
    where_sql = cur.statements[0][0]
    assert "kind = %s" in where_sql and "verified = TRUE" in where_sql


def test_exp_confirm_lifecycle():
    # flip path
    cur = FakeCursor(fetchone=(False,))
    con = FakeConn(cur)
    assert pg.exp_confirm(con, "exp-1") is True
    assert any(s.startswith("UPDATE") for s, _ in cur.statements)
    # already verified
    cur2 = FakeCursor(fetchone=(True,))
    with pytest.raises(ValueError):
        pg.exp_confirm(FakeConn(cur2), "exp-1")
    # missing
    cur3 = FakeCursor(fetchone=None)
    with pytest.raises(KeyError):
        pg.exp_confirm(FakeConn(cur3), "nope")


def test_pg_experience_store_uses_pg(monkeypatch):
    from app.memory.experience_store import PgExperienceStore
    cur = FakeCursor(fetchall=[])
    monkeypatch.setattr(pg, "connect", lambda: FakeConn(cur))
    store = PgExperienceStore()
    exp = store.record("decision", "p1", {"a": 1})
    assert exp.id.startswith("exp-")
    assert any("INSERT INTO genesis_experience" in s for s, _ in cur.statements)
    assert store.query(project="p1") == []


def test_pg_experience_store_no_pg_raises(monkeypatch):
    from app.memory.experience_store import PgExperienceStore
    monkeypatch.setattr(pg, "connect", lambda: None)
    with pytest.raises(ConnectionError):
        PgExperienceStore()


def test_memory_service_falls_back_to_files(monkeypatch, tmp_path):
    from app.memory.memory_service import MemoryService
    monkeypatch.delenv("DATABASE_URL", raising=False)
    svc = MemoryService(tmp_path, project="t1")
    exp = svc.remember("decision", {"a": 1})
    assert svc.verified_knowledge() == []
    assert svc.recall("anything") == [] or isinstance(svc.recall("x"), list)
    assert exp.project == "t1"


def test_shared_rate_limit_paths(monkeypatch):
    from app.api.server import _RateLimiter, _shared_allowed
    # no postgres -> None -> in-memory path still works
    monkeypatch.setattr(pg, "connect", lambda: None)
    assert _shared_allowed("9.9.9.9", 100.0, 300) is None
    rl = _RateLimiter(per_minute=2)
    assert rl.allowed("9.9.9.9") is True
    assert rl.allowed("9.9.9.9") is True
    assert rl.allowed("9.9.9.9") is False
    # shared path: over the limit
    cur = FakeCursor(fetchone=(5,))
    monkeypatch.setattr(pg, "connect", lambda: FakeConn(cur))
    assert _shared_allowed("1.1.1.1", 100.0, 3) is False
    # shared path: under the limit records a hit
    cur2 = FakeCursor(fetchone=(1,))
    monkeypatch.setattr(pg, "connect", lambda: FakeConn(cur2))
    assert _shared_allowed("1.1.1.1", 100.0, 3) is True
    assert any(s.startswith("INSERT INTO genesis_hits") for s, _ in cur2.statements)


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"),
                    reason="needs DATABASE_URL (Railway Postgres)")
def test_live_postgres_roundtrip():
    """Real server only: kv + experience + confirm, then clean up."""
    con = pg.connect()
    assert con is not None
    try:
        assert pg.ensure_schema(con) is True
        pg.kv_set(con, "genesis-test-kv", {"n": 1})
        assert pg.kv_get(con, "genesis-test-kv") == {"n": 1}
        pg.hit(con, "test-ip", 100.0)
        assert pg.count_recent(con, "test-ip", 0.0) >= 1
        pg.exp_insert(con, {"id": "exp-test-1", "time": "2026-01-01T00:00:00+00:00",
                            "kind": "decision", "project": "test",
                            "payload": {"a": 1}, "verified": False})
        rows = pg.exp_query(con, project="test")
        assert any(r["id"] == "exp-test-1" for r in rows)
        assert pg.exp_confirm(con, "exp-test-1") is True
        rows = pg.exp_query(con, project="test", verified_only=True)
        assert any(r["id"] == "exp-test-1" for r in rows)
    finally:
        cur = con.cursor()
        try:
            cur.execute("DELETE FROM genesis_kv WHERE k = 'genesis-test-kv'")
            cur.execute("DELETE FROM genesis_hits WHERE ip = 'test-ip'")
            cur.execute("DELETE FROM genesis_experience WHERE id = 'exp-test-1'")
            con.commit()
        finally:
            cur.close()
            con.close()
