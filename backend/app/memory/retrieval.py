"""Keyword retrieval over experiences and skills.

No vector database: the spec makes semantic retrieval optional, and only
where it improves quality. Plain ranked keyword search is the baseline.
"""

from __future__ import annotations

from .experience_store import Experience
from .skill_registry import Skill


def _score(text: str, terms: list[str]) -> int:
    text = text.lower()
    return sum(1 for t in terms if t in text)


def retrieve(query: str, experiences: list[Experience], skills: list[Skill],
             limit: int = 5) -> list[dict]:
    terms = [t for t in query.lower().split() if len(t) > 2]
    if not terms:
        return []
    ranked: list[tuple[int, dict]] = []
    for e in experiences:
        text = f"{e.kind} {e.project} {e.payload}"
        s = _score(text, terms) + (2 if e.verified else 0)
        if s > 0:
            ranked.append((s, {"type": "experience", "id": e.id,
                              "kind": e.kind, "verified": e.verified,
                              "payload": e.payload}))
    for sk in skills:
        text = f"{sk.description} {sk.procedure} {' '.join(sk.preconditions)}"
        s = _score(text, terms)
        if s > 0:
            ranked.append((s, {"type": "skill", "id": sk.skill_id,
                              "success_rate": round(sk.success_rate, 2),
                              "trials": sk.trials,
                              "description": sk.description}))
    ranked.sort(key=lambda r: -r[0])
    return [r[1] for r in ranked[:limit]]
