"""Approval gate for consequential actions.

In-memory for Phase-2 (persistent approvals table arrives with Postgres in
Phase-6). Requesting an action moves the run to WAITING_FOR_APPROVAL; the
action may only execute after `approve`. Used for: patch apply on user
repos, checkpoint restore, external network, deploys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import count


@dataclass
class Approval:
    id: str
    action: str
    detail: str
    status: str  # PENDING | APPROVED | REJECTED
    time: str


class ApprovalGate:
    def __init__(self) -> None:
        self._items: dict[str, Approval] = {}
        self._ids = count(1)

    def request(self, action: str, detail: str = "") -> Approval:
        item = Approval(
            id=f"APR-{next(self._ids):04d}",
            action=action,
            detail=detail,
            status="PENDING",
            time=datetime.now(timezone.utc).isoformat(),
        )
        self._items[item.id] = item
        return item

    def approve(self, approval_id: str) -> Approval:
        item = self._require_pending(approval_id)
        item.status = "APPROVED"
        return item

    def reject(self, approval_id: str) -> Approval:
        item = self._require_pending(approval_id)
        item.status = "REJECTED"
        return item

    def pending(self) -> list[Approval]:
        return [a for a in self._items.values() if a.status == "PENDING"]

    def _require_pending(self, approval_id: str) -> Approval:
        item = self._items.get(approval_id)
        if item is None:
            raise KeyError(f"unknown approval: {approval_id}")
        if item.status != "PENDING":
            raise ValueError(f"approval {approval_id} already {item.status}")
        return item
