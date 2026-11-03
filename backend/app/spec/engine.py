"""Deterministic NL-spec → structured requirements (no model needed)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass
class Requirement:
    id: str
    description: str
    priority: str
    acceptance: str
    verification: str


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def parse_specification(spec: str) -> list[Requirement]:
    """Split a natural-language spec into requirement records.

    Priority heuristic only: sentences mentioning auth/security/login are P0,
    the rest P1. Empty input yields no requirements (caller must ask for clarity).
    """
    sentences = [s.strip(" .") for s in _SENT_SPLIT.split(spec.strip()) if s.strip()]
    reqs: list[Requirement] = []
    for i, s in enumerate(sentences, 1):
        high = bool(re.search(r"auth|login|secur|password|payment|deploy", s, re.I))
        reqs.append(
            Requirement(
                id=f"REQ-{i:03d}",
                description=s,
                priority="P0" if high else "P1",
                acceptance=f"Demonstrated by execution/test for: {s[:80]}",
                verification="execution+test",
            )
        )
    return reqs


def to_artifacts(reqs: list[Requirement]) -> dict:
    return {"requirements": [asdict(r) for r in reqs]}
