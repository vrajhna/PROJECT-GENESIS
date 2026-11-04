"""Repair loop: propose -> validate -> apply -> retest -> accept/rollback.

The agent is driven with fake routers (same pattern as test_codegen.py);
the loop itself runs REAL pytest against a real broken mini-project, so
accept/rollback claims rest on execution, not mocks.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.agents.repair import RepairAgent, parse_patch, validate_patch
from app.builder.fullstack import _attempt_repairs


def _payload(patches, summary="fix it"):
    text = json.dumps({"patches": patches, "summary": summary})
    return {"output": [{"type": "message", "content": [
        {"type": "output_text", "text": text}]}]}


class FakeRouter:
    def __init__(self, script=None):
        from types import SimpleNamespace
        self.client = SimpleNamespace(config=SimpleNamespace(
            api_key="test-key", primary_model="muse-spark-1.3",
            advanced_model="muse-wonder-1.0", timeout_s=30))
        self._script = list(script) if script else [(True, _payload([]))]
        self.calls = []

    def run(self, task_kind, user_input):
        self.calls.append(task_kind)
        ok, payload = self._script.pop(0) if self._script else (True, _payload([]))
        if not ok:
            return {"ok": False, "error": "model down", "model": "muse-wonder-1.0"}
        return {"ok": True, "data": payload, "model": "muse-wonder-1.0",
                "latency_ms": 7}


GOOD_PATCH = {"path": "calc.py", "find": "return a - b", "replace": "return a + b"}


def test_validate_patch_gates(tmp_path):
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    assert validate_patch(tmp_path, GOOD_PATCH) == (True, "ok")
    assert validate_patch(tmp_path, {"path": "../evil.py",
                                     "find": "x", "replace": "y"})[0] is False
    assert validate_patch(tmp_path, {"path": "/abs.py",
                                     "find": "x", "replace": "y"})[0] is False
    assert validate_patch(tmp_path, {"path": "calc.py", "find": "nope",
                                     "replace": "y"})[0] is False
    assert validate_patch(tmp_path, {"path": "calc.py", "find": "a",
                                     "replace": "y"})[0] is False  # multi-match
    assert validate_patch(tmp_path, {"path": "calc.py", "find": "return a - b",
                                     "replace": "key sk-live-abcdefghij"})[0] is False
    assert validate_patch(tmp_path, {"path": ".venv/lib.py", "find": "x",
                                     "replace": "y"})[0] is False
    assert validate_patch(tmp_path, {"path": "gone.py", "find": "x",
                                     "replace": "y"})[0] is False


def test_parse_patch_shapes():
    doc = parse_patch('{"patches": [{"path": "a.py", "find": "x", "replace": "y"}], "summary": "s"}')
    assert doc["patches"][0]["path"] == "a.py" and doc["summary"] == "s"
    with pytest.raises(ValueError):
        parse_patch("no json here")
    with pytest.raises(ValueError):
        parse_patch('{"files": {}}')


def test_agent_proposes_validated_patch(tmp_path):
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    router = FakeRouter(script=[(True, _payload([GOOD_PATCH]))])
    agent = RepairAgent(router=router)
    res = agent.propose(tmp_path, {"suspected_root_cause": "wrong operator"},
                        "assert add(1, 2) == 3 failed", ["calc.py"])
    assert res["ok"] is True and res["patches"] == [GOOD_PATCH]
    assert router.calls == ["debug repair proposal"]  # routes to advanced


def test_agent_honest_without_key_or_model(tmp_path, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    res = RepairAgent().propose(tmp_path, {}, "boom", [])
    assert res["ok"] is False and "MODEL_API_KEY" in res["error"]
    router = FakeRouter(script=[(False, None)])
    res = RepairAgent(router=router).propose(tmp_path, {}, "boom", ["calc.py"])
    assert res["ok"] is False and "model call failed" in res["error"]


def _broken_project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (proj / "test_calc.py").write_text(
        "from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    return proj


def _notes():
    return []


def test_loop_fixes_and_proves_with_real_pytest(tmp_path):
    proj = _broken_project(tmp_path)
    agent = RepairAgent(router=FakeRouter(script=[(True, _payload([GOOD_PATCH]))]))
    fixed, out, passed, records = _attempt_repairs(
        proj, sys.executable, 0, {"suspected_root_cause": "wrong operator"},
        "1 failed", ["calc.py"],
        lambda *a: _notes(), agent=agent, test_args=["-q", "-rf"])
    assert fixed is True and passed == 1
    assert "return a + b" in (proj / "calc.py").read_text()
    assert records[0]["ok"] is True and records[0]["stage"] == "retest"
    # every capability went through the audited registry, not raw calls
    assert "read_file" in records[0]["tools"]
    assert "apply_patch" in records[0]["tools"]


def test_loop_rolls_back_byte_exact_when_patch_fails(tmp_path):
    proj = _broken_project(tmp_path)
    before = (proj / "calc.py").read_bytes()
    still_bad = {"path": "calc.py", "find": "return a - b", "replace": "return a - b * 2"}
    agent = RepairAgent(router=FakeRouter(
        script=[(True, _payload([still_bad])), (True, _payload([still_bad]))]))
    fixed, out, passed, records = _attempt_repairs(
        proj, sys.executable, 0, {}, "1 failed", ["calc.py"],
        lambda *a: _notes(), agent=agent, test_args=["-q", "-rf"])
    assert fixed is False and passed == 0
    assert len(records) == 2  # bounded at max attempts
    assert (proj / "calc.py").read_bytes() == before  # byte-exact rollback


def test_loop_stops_when_no_model(tmp_path):
    proj = _broken_project(tmp_path)
    fixed, out, passed, records = _attempt_repairs(
        proj, sys.executable, 0, {}, "1 failed", ["calc.py"],
        lambda *a: _notes(),
        agent=RepairAgent(router=FakeRouter(script=[(False, None)])),
        test_args=["-q", "-rf"])
    assert fixed is False and len(records) == 1
    assert records[0]["stage"] == "propose"
