"""Memory service facade: suggestions quarantined until execution confirms them."""

from __future__ import annotations

import json
from pathlib import Path

from .experience_store import Experience, ExperienceStore
from .retrieval import retrieve
from .skill_registry import Skill, SkillRegistry


class MemoryService:
    """Separates model suggestions from experimentally confirmed knowledge.

    Anything unverified enters as kind="suggestion" (verified=False) and is
    invisible to verified-only consumers until confirm() flips it after a
    real execution proves it.
    """

    def __init__(self, root: Path, project: str = "genesis") -> None:
        base = root / ".genesis"
        self.store = ExperienceStore(base / "experiences.jsonl")
        self.skills = SkillRegistry(base / "skills.json")
        self.project = project

    def remember(self, kind: str, payload: dict, verified: bool = False) -> Experience:
        return self.store.record(kind, self.project, payload, verified)

    def suggest(self, payload: dict) -> Experience:
        return self.store.record("suggestion", self.project, payload, verified=False)

    def confirm(self, experience_id: str) -> Experience:
        """Promote a suggestion to verified knowledge after execution proof."""
        if not self.store.path.exists():
            raise KeyError(experience_id)
        rows = self.store.path.read_text(encoding="utf-8").splitlines()
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
        self.store.path.write_text("\n".join(out) + "\n", encoding="utf-8")
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
