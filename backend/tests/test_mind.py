"""Memory (VII), improvement (VIII), schema (IX). All execution is real."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.agents.roles import MemoryEngine
from app.db.schema import EXPECTED, to_postgres_ddl, validate_schema
from app.improve.experiments import ExperimentRunner
from app.memory.memory_service import MemoryService


def test_memory_suggestions_quarantined_until_confirmed(tmp_path: Path):
    svc = MemoryService(tmp_path, project="demo")
    assert svc.verified_knowledge() == []
    assert svc.recall("anything") == []
    sug = svc.suggest({"claim": "pytest is green"})
    assert svc.verified_knowledge() == []  # suggestions invisible to verified consumers
    assert any(r["id"] == sug.id for r in svc.recall("pytest"))
    confirmed = svc.confirm(sug.id)
    assert confirmed.verified is True
    assert len(svc.verified_knowledge()) == 1
    try:
        svc.confirm(sug.id)
    except ValueError:
        pass
    else:
        raise AssertionError("double confirm must raise")
    try:
        svc.confirm("exp-missing")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown id must raise")


def test_memory_engine_compat_layer(tmp_path: Path):
    from app.builder.files import GenesisWorkspace
    mem = MemoryEngine(GenesisWorkspace(tmp_path))
    mem.record("success", "checkpoint restore works", "sha abc")
    assert len(mem.retrieve("checkpoint")) == 1


def test_skill_promotion_needs_trials_and_evidence(tmp_path: Path):
    svc = MemoryService(tmp_path, project="demo")
    sk = svc.register_skill("run pytest", ["repo exists"], "python3 -m pytest -q", ["needs pytest"])
    assert sk.promoted is False and sk.success_rate == 0.0
    svc.skills.record_trial(sk.skill_id, True, "11 passed")
    svc.skills.record_trial(sk.skill_id, True, "12 passed")
    assert svc.skills.get(sk.skill_id).promoted is False  # only 2 trials
    svc.skills.record_trial(sk.skill_id, True, "12 passed")
    got = svc.skills.get(sk.skill_id)
    assert got.promoted is True and got.success_rate == 1.0
    assert any("11 passed" in e for e in got.evidence)
    assert svc.recall("pytest")[0]["type"] == "skill"


def _fixture_repo(broken_calc: bool) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="genesis-fix-"))
    body = "return a - b" if broken_calc else "return a + b"
    (tmp / "calc.py").write_text(f"def add(a, b):\n    {body}\n")
    (tmp / "test_calc.py").write_text(
        "from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    return tmp


def test_experiment_retains_genuine_fix():
    repo = _fixture_repo(broken_calc=True)
    try:
        runner = ExperimentRunner(repo)
        res = runner.evaluate("fix add", "calc.py", "return a - b", "return a + b")
        assert res.ok and res.retained is True
        assert res.baseline_passed == 0 and res.candidate_passed >= 1
        assert "retained" in res.reason
        assert (repo / "calc.py").read_text() == "def add(a, b):\n    return a - b\n"
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_experiment_rejects_breaking_candidate():
    repo = _fixture_repo(broken_calc=False)
    try:
        runner = ExperimentRunner(repo)
        res = runner.evaluate("break add", "calc.py", "return a + b", "return a - b")
        assert res.ok and res.retained is False
        assert res.baseline_passed >= 1 and res.candidate_passed == 0
        assert "real tree untouched" in res.reason
        assert (repo / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_experiment_critical_path_needs_approval():
    repo = _fixture_repo(broken_calc=False)
    try:
        runner = ExperimentRunner(repo)
        res = runner.evaluate("touch kernel", "app/orchestrator/x.py", "a", "b")
        assert res.ok is False and "approv" in res.reason.lower()
        assert res.retained is False
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_schema_valid_and_postgres_ddl_complete():
    assert validate_schema() == []
    ddl = to_postgres_ddl()
    for entity in EXPECTED:
        assert f"CREATE TABLE {entity} (" in ddl, entity
    assert "UUID PRIMARY KEY DEFAULT gen_random_uuid()" in ddl
    assert "REFERENCES projects(id)" in ddl
    assert "timestamptz" in ddl.lower()
    bad = {"users": {"columns": {"id": "INT PK"}, "fks": {}, "indexes": []}}
    problems = validate_schema(bad)
    assert any("entity set mismatch" in p for p in problems)
    assert any("UUID PK" in p for p in problems)


def test_run_pytest_helper_handles_missing_dir():
    from app.improve.experiments import _run_pytest
    ok, n, tail = _run_pytest(Path("/nonexistent-dir-xyz"))
    assert ok is False
