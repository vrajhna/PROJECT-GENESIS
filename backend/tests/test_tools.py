"""Tool registry + memory engine. Proposed calls are validated, never trusted."""

import shutil

import pytest

from app.agents.roles import MemoryEngine
from app.builder.approvals import ApprovalGate
from app.builder.checkpoints import init_repo
from app.builder.files import GenesisWorkspace
from app.tools.registry import TOOLS, ToolRegistry

git = shutil.which("git")
needs_git = pytest.mark.skipif(git is None, reason="git not installed")


def make_registry(tmp_path):
    ws = GenesisWorkspace(tmp_path)
    return ToolRegistry(ws, ApprovalGate())


def test_registry_declares_fourteen_tools_with_contracts():
    names = {t.name for t in TOOLS}
    assert len(TOOLS) == 14 and len(names) == 14
    for t in TOOLS:
        assert t.required is not None and t.permission in ("open", "approval")
        assert t.timeout_s > 0 and t.description


def test_unknown_tool_and_schema_rejection(tmp_path):
    reg = make_registry(tmp_path)
    assert reg.call("nope")["ok"] is False
    res = reg.call("read_file", {})
    assert res["ok"] is False and "path" in res["error"]


@needs_git
def test_create_read_search_checkpoint_roundtrip(tmp_path):
    init_repo(tmp_path)
    reg = make_registry(tmp_path)
    assert reg.call("create_file", {"path": "a.txt", "content": "hello"})["ok"] is True
    assert reg.call("read_file", {"path": "a.txt"})["content"] == "hello"
    assert reg.call("apply_patch", {"path": "a.txt", "find": "hello", "replace": "hi"})["ok"] is True
    hits = reg.call("search_code", {"query": "hi"})["hits"]
    assert any("a.txt" in h for h in hits)
    sha = reg.call("create_git_checkpoint", {"message": "t1"})
    assert sha["ok"] is True and len(sha["sha"]) == 40


def test_approval_gate_blocks_shell_and_restore(tmp_path):
    reg = make_registry(tmp_path)
    blocked = reg.call("run_command", {"argv": ["echo", "hi"]})
    assert blocked["ok"] is False and "approval" in blocked["error"]
    assert reg.call("restore_checkpoint", {"sha": "abc"})["ok"] is False
    item = reg.call("request_approval", {"action": "run_command", "detail": "echo"})
    assert item["ok"] is True
    ok = reg.call("run_command", {"argv": ["echo", "hi"]}, approved=True)
    assert ok["ok"] is True and "hi" in ok["output"]
    assert "hi" in reg.call("get_runtime_logs", {})["logs"]
    assert reg.call("run_command", {"argv": "echo hi"})["ok"] is False  # string = shell


def test_run_tests_and_docs_through_registry(tmp_path):
    reg = make_registry(tmp_path)
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    res = reg.call("run_tests", {})
    assert res["ok"] is True and res["data"]["passed"] >= 1
    stored = reg.call("get_test_results", {})
    assert "passed" in stored["result"]
    assert reg.call("generate_documentation", {})["ok"] is True
    assert (tmp_path / "RUNBOOK.md").exists()
    assert reg.call("inspect_project", {})["ok"] is True
    assert reg.call("inspect_dependencies", {})["ok"] is True


def test_memory_record_and_retrieve(tmp_path):
    mem = MemoryEngine(GenesisWorkspace(tmp_path))
    assert mem.retrieve("anything") == []
    mem.record("success", "pytest green after checkpoint restore", "11 passed")
    mem.record("failure", "broke on missing key", "MODEL_API_KEY unset")
    hits = mem.retrieve("pytest")
    assert len(hits) == 1 and hits[0]["kind"] == "success"
    with pytest.raises(ValueError):
        mem.record("rumor", "unverified claim")


def test_interpretation_and_regression_fields(tmp_path):
    from app.agents.roles import TestingAgent
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    res = TestingAgent().run(tmp_path)
    assert "Regression: baseline recorded." in res.data["interpretation"]
    assert "pytest-cov not installed" in res.data["interpretation"]
    res2 = TestingAgent().run(tmp_path)
    assert "no change" in res2.data["interpretation"]
