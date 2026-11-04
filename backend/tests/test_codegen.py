"""Model-driven codegen (M4-core): the model writes, the pipeline proves.

All network-free except the explicitly skipped live test.
"""

import json

import pytest

from app.builder import codegen
from app.intelligence.meta_client import MetaClient, MetaConfig


GOOD_FILES = {
    "frontend/index.html": "<html><body><canvas id='b'></canvas></body></html>",
    "frontend/app.js": "console.log('game');",
    "frontend/style.css": "body{}",
    "backend/server.py": "# stdlib server\nBIND = (\"127.0.0.1\", 8000)\n",
    "tests/test_app.py": "def test_x():\n    assert True\n",
    "requirements.txt": "pytest\n",
}


def _payload(files):
    return {"output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps({"files": files})}]}]}


class FakeClient:
    def __init__(self, payload=None, ok=True, error="boom"):
        from types import SimpleNamespace
        self.config = SimpleNamespace(
            api_key="test-key",
            primary_model="muse-spark-1.3",
            advanced_model="muse-wonder-1.0",
            timeout_s=30)
        self._payload = payload
        self._ok = ok
        self._error = error

    def respond(self, model, user_input, task="adhoc",
                tools=None, response_format=None, effort=None):
        if not self._ok:
            return {"ok": False, "error": self._error}
        return {"ok": True, "data": self._payload, "latency_ms": 42}


class FakeRouter:
    def __init__(self, client=None, script=None):
        from types import SimpleNamespace
        self.client = client or SimpleNamespace(config=SimpleNamespace(
            api_key="test-key",
            primary_model="muse-spark-1.3",
            advanced_model="muse-wonder-1.0",
            timeout_s=30))
        self.seen_kind = None
        # default: Wonder succeeds with the canonical good files
        self._script = (list(script) if script is not None
                        else [(True, _payload(GOOD_FILES), "muse-wonder-1.0")])
        self.calls = []

    def run(self, task_kind, user_input):
        self.seen_kind = task_kind
        self.calls.append(task_kind)
        ok, payload_or_err, model = self._script.pop(0)
        if not ok:
            return {"ok": False, "error": payload_or_err, "model": model,
                    "task_kind": task_kind}
        return {"ok": True, "data": payload_or_err, "model": model,
                "latency_ms": 42, "task_kind": task_kind}


def test_ok_path_uses_wonder_and_records_author():
    router = FakeRouter()
    out = generate(router=router)
    assert out["ok"] is True
    assert router.seen_kind == "multi-file codegen"
    assert out["model"] == "muse-wonder-1.0"
    assert set(out["files"]) >= codegen.REQUIRED_FILES


def generate(**kw):
    return codegen.generate_with_model(
        "Build me a flappy game", [{"id": "REQ-001", "description": "flap"}],
        ["score"], False, "flappy", **kw)


def test_model_not_found_falls_back_to_primary_then_writes():
    router = FakeRouter(None, script=[
        (False, 'HTTP 404: {"error": {"code": "model_not_found"}}',
         "muse-wonder-1.0"),
        (True, _payload(GOOD_FILES), "muse-spark-1.3"),
    ])
    out = generate(router=router)
    assert out["ok"] is True
    assert out["model"] == "muse-spark-1.3"
    assert router.calls == ["multi-file codegen", "routine codegen"]


def test_both_models_down_reports_tried_models():
    router = FakeRouter(None, script=[
        (False, "HTTP 404 model_not_found", "muse-wonder-1.0"),
        (False, "HTTP 503 overloaded", "muse-spark-1.3"),
    ])
    out = generate(router=router)
    assert out["ok"] is False and out["fallback"] is True
    assert "muse-wonder-1.0" in out["error"] and "muse-spark-1.3" in out["error"]


def test_non_404_error_skips_primary_and_falls_back():
    router = FakeRouter(None, script=[
        (False, "HTTP 500 burned toast", "muse-wonder-1.0"),
    ])
    out = generate(router=router)
    assert out["ok"] is False
    assert router.calls == ["multi-file codegen"]


def test_no_key_falls_back_without_network():
    cfg = MetaConfig(api_key="", base_url="https://api.meta.ai/v1",
                     primary_model="muse-spark-1.3",
                     advanced_model="muse-wonder-1.0")
    out = codegen.generate_with_model("spec", [], [], False, "none",
                                      client=MetaClient(cfg))
    assert out["ok"] is False and out["fallback"] is True


def test_model_error_falls_back():
    router = FakeRouter(script=[(False, "boom", "muse-wonder-1.0")])
    out = generate(router=router)
    assert out["ok"] is False and out["fallback"] is True


def test_non_json_output_rejected():
    payload = {"output": [{"type": "message",
                           "content": [{"type": "output_text",
                                        "text": "no json here"}]}]}
    out = generate(router=FakeRouter(script=[(True, payload, 'muse-wonder-1.0')]))
    assert out["ok"] is False and "JSON" in out["error"]


def test_traversal_path_rejected():
    bad = dict(GOOD_FILES)
    bad["../evil.py"] = "x"
    out = generate(router=FakeRouter(script=[(True, _payload(bad), 'muse-wonder-1.0')]))
    assert out["ok"] is False and "not allowed" in out["error"]


def test_secret_in_output_rejected():
    bad = dict(GOOD_FILES)
    bad["backend/server.py"] += '\nKEY = "sk-live-abcdefgh12345678"\n'
    out = generate(router=FakeRouter(script=[(True, _payload(bad), 'muse-wonder-1.0')]))
    assert out["ok"] is False and "secret" in out["error"]


def test_missing_required_file_rejected():
    thin = {k: v for k, v in GOOD_FILES.items() if k != "tests/test_app.py"}
    out = generate(router=FakeRouter(script=[(True, _payload(thin), 'muse-wonder-1.0')]))
    assert out["ok"] is False and "missing" in out["error"]


def test_localhost_bind_required():
    bad = dict(GOOD_FILES)
    bad["backend/server.py"] = "# binds everywhere\nBIND = (\"0.0.0.0\", 8000)\n"
    out = generate(router=FakeRouter(script=[(True, _payload(bad), 'muse-wonder-1.0')]))
    assert out["ok"] is False and "localhost" in out["error"]


def test_extract_text_shapes():
    assert codegen.extract_text(
        {"output": [{"content": [{"type": "output_text",
                                  "text": "hi"}]}]}) == "hi"
    assert codegen.extract_text({"text": "yo"}) == "yo"
    assert codegen.extract_text({}) == ""
    assert codegen.extract_text({"output": "nope"}) == ""


@pytest.mark.skipif(not __import__("os").environ.get("MODEL_API_KEY"),
                    reason="needs a real Meta key (Railway has it)")
def test_live_wonder_writes_an_app():
    out = codegen.generate_with_model(
        "Build a tiny click-counter page with a reset button.",
        [{"id": "REQ-001", "description": "button increments a number"},
         {"id": "REQ-002", "description": "reset button zeroes it"}],
        [], False, "none")
    assert out["ok"] is True, out.get("error")
    assert "wonder" in out["model"]
