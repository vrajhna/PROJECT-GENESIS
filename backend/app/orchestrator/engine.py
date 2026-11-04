"""Central orchestrator: task graph + shared, persisted project context.

The orchestrator is the brain. It decomposes a build into tasks with lanes
and dependencies, dispatches them to specialized agent workers, and keeps
ALL shared state in one BuildContext persisted at `.genesis/context.json`.
Agents never call each other directly — evidence, decisions and verdicts
flow through the context, so every task is observable, attributable and
debuggable after the fact. The builders remain the executors; this module
owns state and sequencing truth. Recording never breaks a build: every
filesystem touch is best-effort.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

TASK_FLOW: list[dict] = [
    {"kind": "understand", "lane": "architect", "needs": []},
    {"kind": "plan", "lane": "architect", "needs": ["understand"]},
    {"kind": "generate", "lane": "builder", "needs": ["plan"]},
    {"kind": "venv", "lane": "testing", "needs": ["generate"]},
    {"kind": "install", "lane": "testing", "needs": ["venv"]},
    {"kind": "start", "lane": "testing", "needs": ["install"]},
    {"kind": "test", "lane": "testing", "needs": ["start"]},
    {"kind": "diagnose", "lane": "debugger", "needs": ["test"]},
    {"kind": "repair", "lane": "debugger", "needs": ["diagnose"]},
    {"kind": "review", "lane": "review", "needs": ["test"]},
    {"kind": "secure", "lane": "review", "needs": ["review", "repair"]},
    {"kind": "logs", "lane": "testing", "needs": ["test"]},
    {"kind": "retest", "lane": "testing", "needs": ["secure"]},
    {"kind": "verify", "lane": "review", "needs": ["retest"]},
]

STATES = ("queued", "running", "done", "failed", "blocked", "skipped")


class BuildContext:
    """Shared project state every agent reads and writes through."""

    def __init__(self, spec: str, workdir: Path) -> None:
        self.spec = spec
        self.workdir = Path(workdir)
        self.data: dict = {"requirements": [], "decisions": [],
                           "diagnosis": None, "findings": [],
                           "repairs": [], "author": "", "verdict": ""}
        self.tasks: list[dict] = [
            {"kind": t["kind"], "lane": t["lane"], "needs": list(t["needs"]),
             "state": "queued", "detail": "", "started": 0.0, "finished": 0.0}
            for t in TASK_FLOW]
        self.created = time.time()

    @property
    def path(self) -> Path:
        return self.workdir / ".genesis" / "context.json"

    def task(self, kind: str) -> dict | None:
        for t in self.tasks:
            if t["kind"] == kind:
                return t
        return None

    def task_states(self) -> list[dict]:
        return [{"kind": t["kind"], "lane": t["lane"], "state": t["state"],
                 "detail": t["detail"]} for t in self.tasks]

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            doc = {"spec": self.spec[:2000], "created": self.created,
                   "data": self.data, "tasks": self.tasks}
            self.path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        except OSError:
            pass  # observability must never break the build

    @classmethod
    def load(cls, workdir: Path) -> "BuildContext | None":
        try:
            doc = json.loads((Path(workdir) / ".genesis" / "context.json")
                             .read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        ctx = cls(doc.get("spec", ""), workdir)
        ctx.data = doc.get("data") or ctx.data
        saved = {t.get("kind"): t for t in doc.get("tasks") or []}
        for t in ctx.tasks:
            if t["kind"] in saved:
                t.update(saved[t["kind"]])
        ctx.created = doc.get("created", ctx.created)
        return ctx


class Orchestrator:
    """Owns the task graph for one build. Workers report through record_step."""

    def __init__(self, context: BuildContext) -> None:
        self.context = context

    @classmethod
    def open(cls, spec: str, workdir: Path) -> "Orchestrator":
        ctx = BuildContext(spec, workdir)
        orch = cls(ctx)
        orch.save()
        return orch

    def plan(self) -> list[dict]:
        return [{"kind": t["kind"], "lane": t["lane"],
                 "needs": list(t["needs"])} for t in self.context.tasks]

    def record_step(self, name: str, ok: bool, detail: str = "",
                    lane: str = "") -> None:
        task = self.context.task(name)
        if task is None:
            return
        now = time.time()
        if not task["started"]:
            task["started"] = now
        task["finished"] = now
        task["state"] = "done" if ok else "failed"
        task["detail"] = (detail or "")[:300]
        if lane:
            task["lane"] = lane
        self.save()

    def set(self, key: str, value) -> None:
        self.context.data[key] = value
        self.save()

    def save(self) -> None:
        self.context.save()
