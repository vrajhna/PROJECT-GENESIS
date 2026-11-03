"""Agent roles + end-to-end pipeline. All execution is real."""

from pathlib import Path

from app.agents.roles import (ArchitectAgent, BuilderAgent, DebuggerAgent, ReviewerAgent,
                              TestingAgent)
from app.builder.files import GenesisWorkspace
from app.run import run_pipeline

SPEC = "Users can register and log in securely. Users can create projects and tasks."


def test_architect_extracts_or_asks():
    res = ArchitectAgent().run(SPEC)
    assert res.ok and len(res.data["requirements"]) == 2
    assert res.data["requirements"][0]["priority"] == "P0"
    blocked = ArchitectAgent().run("   ")
    assert blocked.ok is False and blocked.data["needs_clarification"] is True


def test_builder_scaffolds_and_tests_pass(tmp_path: Path):
    ws = GenesisWorkspace(tmp_path)
    arch = ArchitectAgent().run(SPEC)
    build = BuilderAgent(ws).scaffold(arch.data["requirements"])
    assert build.ok and set(build.data["files"]) == {"solution.py", "test_solution.py", "SPEC.json"}
    test = TestingAgent().run(tmp_path)
    assert test.ok, test.summary
    assert test.data["exit_code"] == 0 and test.data["passed"] >= 2


def test_reviewer_flags_secrets_and_missing_tests(tmp_path: Path):
    (tmp_path / "leak.py").write_text('KEY = "sk-live-abcdefgh12345678"\n')
    findings = ReviewerAgent().run(tmp_path).data["findings"]
    assert any("leak.py" in f for f in findings)
    empty = tmp_path / "empty"
    empty.mkdir()
    assert any("no tests" in f for f in ReviewerAgent().run(empty).data["findings"])


def test_debugger_structured_diagnosis():
    diag = DebuggerAgent().run({"id": "F-007", "category": "test-failure",
                                "logs": "FAILED test_x - assert 1 == 2",
                                "files": ["x.py"]}).data
    for key in ("failure_id", "failure_category", "suspected_root_cause",
                "supporting_evidence", "alternative_explanations", "affected_files",
                "confidence_estimate", "proposed_repair", "tests_required"):
        assert key in diag, key
    assert diag["failure_id"] == "F-007"


def test_full_pipeline_verdict_verified(tmp_path: Path):
    report = run_pipeline(SPEC, tmp_path / "demo")
    assert report["verdict"] == "VERIFIED", report
    assert report["states"][-1] == "COMPLETED"
    assert (tmp_path / "demo" / "test_solution.py").exists()
