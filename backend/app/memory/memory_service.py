"""Memory service facade: suggestions quarantined until execution confirms them."""

from __future__ import annotations

import json
from pathlib import Path

from .experience_store import Experience, ExperienceStore, PgExperienceStore
from .retrieval import retrieve
from .skill_registry import Skill, SkillRegistry


def _pg_store():
    """PgExperienceStore when Postgres is live, else None. Never raises."""
    try:
        from ..db import pg as _pg
        if not _pg.available():
            return None
        return PgExperienceStore()
    except Exception:
        return None


class MemoryService:
    """Separates model suggestions from experimentally confirmed knowledge.

    Anything unverified enters as kind="suggestion" (verified=False) and is
    invisible to verified-only consumers until confirm() flips it after a
    real execution proves it.
    """

    def __init__(self, root: Path, project: str = "genesis") -> None:
        base = root / ".genesis"
        self.store = _pg_store() or ExperienceStore(base / "experiences.jsonl")
        self._file_base = base
        self.skills = SkillRegistry(base / "skills.json")
        self.project = project

    def remember(self, kind: str, payload: dict, verified: bool = False) -> Experience:
        return self.store.record(kind, self.project, payload, verified)

    def suggest(self, payload: dict) -> Experience:
        return self.store.record("suggestion", self.project, payload, verified=False)

    def confirm(self, experience_id: str) -> Experience:
        """Promote a suggestion to verified knowledge after execution proof."""
        store = self.store
        if hasattr(store, "confirm"):
            try:
                return store.confirm(experience_id)
            except (KeyError, ValueError):
                raise
            except Exception:
                # Postgres hiccup mid-flight: degrade to the file ledger
                # rather than crash. May raise KeyError if it lived only in pg.
                store = ExperienceStore(self._file_base / "experiences.jsonl")
        if not store.path.exists():
            raise KeyError(experience_id)
        rows = store.path.read_text(encoding="utf-8").splitlines()
        out = []
        found = None
        for line in rows:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("id") == experience_id:
                if row.get("verified"):
                    raise ValueError("already verified")
                row["verified"] = True
                found = row
            out.append(json.dumps(row))
        if found is None:
            raise KeyError(experience_id)
        store.path.write_text("\n".join(out) + "\n", encoding="utf-8")
        return Experience(**{k: found[k] for k in
                             ("id", "time", "kind", "project", "payload", "verified")})

    def verified_knowledge(self) -> list[Experience]:
        return self.store.query(project=self.project, verified_only=True)

    def recall(self, query: str, limit: int = 5) -> list[dict]:
        return retrieve(query, self.store.query(project=self.project),
                        self.skills.list(), limit)

    def register_skill(self, description: str, preconditions: list[str],
                       procedure: str, limitations: list[str] | None = None) -> Skill:
        return self.skills.register(description, preconditions, procedure, limitations)
