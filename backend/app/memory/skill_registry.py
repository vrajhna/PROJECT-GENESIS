"""Skill registry: promotion only through recorded trials with evidence."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Skill:
    skill_id: str
    description: str
    preconditions: list[str]
    procedure: str
    evidence: list[str] = field(default_factory=list)
    trials: int = 0
    successes: int = 0
    limitations: list[str] = field(default_factory=list)
    version: str = "1"

    @property
    def success_rate(self) -> float:
        return self.successes / self.trials if self.trials else 0.0

    @property
    def promoted(self) -> bool:
        return self.trials >= 3 and self.success_rate >= 0.8


class SkillRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except ValueError:
            return {}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def register(self, description: str, preconditions: list[str], procedure: str,
                 limitations: list[str] | None = None) -> Skill:
        data = self._load()
        skill = Skill(skill_id=f"sk-{uuid.uuid4().hex[:8]}", description=description,
                      preconditions=preconditions, procedure=procedure,
                      limitations=limitations or [])
        data[skill.skill_id] = asdict(skill)
        self._save(data)
        return skill

    def record_trial(self, skill_id: str, success: bool, evidence: str) -> Skill:
        data = self._load()
        if skill_id not in data:
            raise KeyError(f"unknown skill: {skill_id}")
        row = data[skill_id]
        row["trials"] += 1
        row["successes"] += 1 if success else 0
        row["evidence"].append(f"{datetime.now(timezone.utc).isoformat()} {'PASS' if success else 'FAIL'}: {evidence}")
        data[skill_id] = row
        self._save(data)
        return Skill(**row)

    def get(self, skill_id: str) -> Skill:
        data = self._load()
        if skill_id not in data:
            raise KeyError(f"unknown skill: {skill_id}")
        return Skill(**data[skill_id])

    def list(self) -> list[Skill]:
        return [Skill(**row) for row in self._load().values()]
