"""Call registry: every Meta API call recorded. Stdlib only."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelCall:
    id: str
    model: str
    task: str
    latency_ms: int
    ok: bool
    error: str = ""
    retries: int = 0
    tokens: int = 0
    cost: float = 0.0


class ModelRegistry:
    """In-memory ledger (persistent table arrives with Postgres)."""

    def __init__(self) -> None:
        self.calls: list[ModelCall] = []

    def record(self, call: ModelCall) -> None:
        self.calls.append(call)

    def summary(self) -> dict:
        total = len(self.calls)
        ok = sum(1 for c in self.calls if c.ok)
        lat = [c.latency_ms for c in self.calls]
        by_model: dict[str, int] = {}
        for c in self.calls:
            by_model[c.model] = by_model.get(c.model, 0) + 1
        return {
            "total": total,
            "ok": ok,
            "errors": total - ok,
            "avg_latency_ms": int(sum(lat) / len(lat)) if lat else 0,
            "by_model": by_model,
        }

    def last(self, n: int = 5) -> list[ModelCall]:
        return self.calls[-n:]
