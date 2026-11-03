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
