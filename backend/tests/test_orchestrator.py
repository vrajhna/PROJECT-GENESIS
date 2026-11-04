"""Orchestrator: task graph, shared persisted context, delegation spine."""

import json
from pathlib import Path

from app.orchestrator.engine import BuildContext, Orchestrator, TASK_FLOW


def test_open_persists_context_and_plan(tmp_path: Path):
    orch = Orchestrator.open("Build me a blog", tmp_path)
    ctx_file = tmp_path / ".genesis" / "context.json"
    assert ctx_file.exists()
    doc = json.loads(ctx_file.read_text())
    assert doc["spec"] == "Build me a blog"
    assert len(doc["tasks"]) == len(TASK_FLOW)
    assert all(t["state"] == "queued" for t in doc["tasks"])
    plan = orch.plan()
    kinds = [p["kind"] for p in plan]
    assert kinds.index("repair") > kinds.index("diagnose") > kinds.index("test")
    assert "secure" in kinds and kinds.index("secure") > kinds.index("review")


def test_record_step_transitions_and_persists(tmp_path: Path):
    orch = Orchestrator.open("spec", tmp_path)
    orch.record_step("understand", True, "4 requirements", lane="architect")
    task = orch.context.task("understand")
    assert task["state"] == "done" and task["started"] > 0
    orch.record_step("test", False, "1 failed", lane="testing")
    assert orch.context.task("test")["state"] == "failed"
    orch.record_step("nonexistent", True, "ignored")  # never raises
    loaded = BuildContext.load(tmp_path)
    assert loaded is not None
    assert loaded.task("understand")["state"] == "done"
    assert loaded.task("test")["state"] == "failed"


def test_set_roundtrips_shared_state(tmp_path: Path):
    orch = Orchestrator.open("spec", tmp_path)
    orch.set("requirements", [{"id": "R-001", "description": "blog posts"}])
    orch.set("diagnosis", {"suspected_root_cause": "wrong operator"})
    orch.set("verdict", "VERIFIED")
    loaded = BuildContext.load(tmp_path)
    assert loaded.data["requirements"][0]["id"] == "R-001"
    assert loaded.data["diagnosis"]["suspected_root_cause"] == "wrong operator"
    assert loaded.data["verdict"] == "VERIFIED"


def test_build_writes_orchestrated_context(tmp_path: Path):
    # End-to-end proof the full-stack builder runs on the orchestrator spine:
    # context.json lands in the workdir with the verdict + task states.
    from app.builder.fullstack import build_fullstack
    report = build_fullstack("Build me a blog where I can publish posts. "
                             "No login needed.", tmp_path / "blog")
    assert report["verdict"] == "VERIFIED", report
    ctx = BuildContext.load(tmp_path / "blog")
    assert ctx is not None
    states = {t["kind"]: t["state"] for t in ctx.task_states()}
    assert states["understand"] == "done" and states["test"] == "done"
    assert ctx.data["verdict"] == "VERIFIED"
    assert ctx.data["requirements"]
    tasks = {t["kind"]: t["state"] for t in report["tasks"]}
    assert tasks["secure"] == "done"
