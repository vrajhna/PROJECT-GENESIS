"""Append-only experience store. File-backed today, Postgres in Phase 6."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

KINDS = frozenset({
    "project_fact", "requirement", "decision", "execution", "test_result",
    "diagnosis", "repair", "skill", "knowledge", "limitation", "suggestion",
})


@dataclass
class Experience:
    id: str
    time: str
    kind: str
    project: str
    payload: dict
    verified: bool


class ExperienceStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def record(self, kind: str, project: str, payload: dict,
               verified: bool = False) -> Experience:
        if kind not in KINDS:
            raise ValueError(f"unknown experience kind: {kind}")
        exp = Experience(id=f"exp-{uuid.uuid4().hex[:12]}",
                         time=datetime.now(timezone.utc).isoformat(),
                         kind=kind, project=project,
                         payload=payload, verified=verified)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(exp)) + "\n")
        return exp

    def query(self, kind: str | None = None, project: str | None = None,
              verified_only: bool = False) -> list[Experience]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if kind and row.get("kind") != kind:
                continue
            if project and row.get("project") != project:
                continue
            if verified_only and not row.get("verified"):
                continue
            out.append(Experience(**{k: row[k] for k in
                                     ("id", "time", "kind", "project", "payload", "verified")}))
        return out


class PgExperienceStore:
    """Postgres-backed twin of ExperienceStore (table genesis_experience).

    Same record/query/confirm contract. Used when DATABASE_URL is live;
    every failure must make the caller fall back to files, never crash.
    """

    def __init__(self) -> None:
        from ..db import pg as _pg
        self._pg = _pg
        con = _pg.connect()
        if con is None:
            raise ConnectionError("postgres unavailable")
        try:
            if not _pg.ensure_schema(con):
                raise ConnectionError("schema not ready")
        finally:
            try:
                con.close()
            except Exception:
                pass

    def _conn(self):
        con = self._pg.connect()
        if con is None:
            raise ConnectionError("postgres unavailable")
        return con

    def record(self, kind: str, project: str, payload: dict,
               verified: bool = False) -> Experience:
        if kind not in KINDS:
            raise ValueError(f"unknown experience kind: {kind}")
        exp = Experience(id=f"exp-{uuid.uuid4().hex[:12]}",
                         time=datetime.now(timezone.utc).isoformat(),
                         kind=kind, project=project,
                         payload=payload, verified=verified)
        con = self._conn()
        try:
            self._pg.exp_insert(con, asdict(exp))
        finally:
            try:
                con.close()
            except Exception:
                pass
        return exp

    def query(self, kind: str | None = None, project: str | None = None,
              verified_only: bool = False) -> list[Experience]:
        con = self._conn()
        try:
            rows = self._pg.exp_query(con, kind=kind, project=project,
                                      verified_only=verified_only)
        finally:
            try:
                con.close()
            except Exception:
                pass
        return [Experience(**r) for r in rows]

    def confirm(self, experience_id: str) -> Experience:
        con = self._conn()
        try:
            self._pg.exp_confirm(con, experience_id)
            rows = self._pg.exp_query(con, limit=5000)
        finally:
            try:
                con.close()
            except Exception:
                pass
        for r in rows:
            if r["id"] == experience_id:
                return Experience(**r)
        raise KeyError(experience_id)
