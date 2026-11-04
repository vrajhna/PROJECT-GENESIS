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


MODEL_APP_FILES = {
    "frontend/index.html": ("<html><head><title>Counter</title>"
                             '<link rel="stylesheet" href="/style.css"></head>'
                             "<body><h1>Counter</h1><canvas id=\"b\"></canvas>"
                             '<script src="/app.js"></script></body></html>'),
    "frontend/app.js": ("fetch('/api/health');\n"
                        "document.addEventListener('click', () => {\n"
                        "  fetch('/api/notes', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: 'n', data: {}})});\n"
                        "});"),
    "frontend/style.css": "body{}",
    "backend/server.py": (
        '"""model-written app (test double)."""\n'
        "import json\n"
        "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
        "NOTES = []\n"
        "class H(BaseHTTPRequestHandler):\n"
        "    def _send(self, payload, code=200):\n"
        "        b = json.dumps(payload).encode()\n"
        "        self.send_response(code)\n"
        "        self.send_header('Content-Type', 'application/json')\n"
        "        self.send_header('Content-Length', str(len(b)))\n"
        "        self.end_headers()\n"
        "        self.wfile.write(b)\n"
        "    def _static(self, name, ctype):\n"
        "        import os as _os\n"
        "        p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'frontend', name)\n"
        "        with open(p, 'rb') as f:\n"
        "            b = f.read()\n"
        "        self.send_response(200)\n"
        "        self.send_header('Content-Type', ctype)\n"
        "        self.send_header('Content-Length', str(len(b)))\n"
        "        self.end_headers()\n"
        "        self.wfile.write(b)\n"
        "    def do_GET(self):\n"
        "        from urllib.parse import urlparse\n"
        "        path = urlparse(self.path).path\n"
        "        if path == '/api/health':\n"
        "            return self._send({'ok': True})\n"
        "        if path in ('/', '/index.html'):\n"
        "            return self._static('index.html', 'text/html; charset=utf-8')\n"
        "        if path == '/app.js':\n"
        "            return self._static('app.js', 'text/javascript; charset=utf-8')\n"
        "        if path == '/style.css':\n"
        "            return self._static('style.css', 'text/css; charset=utf-8')\n"
        "        if path == '/api/notes':\n"
        "            return self._send(NOTES)\n"
        "        return self._send({'error': 'not found'}, 404)\n"
        "    def do_POST(self):\n"
        "        from urllib.parse import urlparse\n"
        "        if urlparse(self.path).path != '/api/notes':\n"
        "            return self._send({'error': 'not found'}, 404)\n"
        "        n = int(self.headers.get('Content-Length') or 0)\n"
        "        body = json.loads(self.rfile.read(n) or b'{}')\n"
        "        NOTES.append({'name': body.get('name', ''), 'data': body.get('data', {})})\n"
        "        return self._send({'ok': True})\n"
        "    def log_message(self, *a):\n"
        "        pass\n"
        "if __name__ == '__main__':\n"
        "    import sys as _sys\n"
        "    port = int(_sys.argv[_sys.argv.index('--port') + 1]) if '--port' in _sys.argv else 8000\n"
        '    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()\n'
    ),
    "tests/test_app.py": (
        "import json\nimport os\nimport urllib.request\n"
        "BASE = 'http://127.0.0.1:' + os.environ.get('GENESIS_APP_PORT', '8000')\n"
        "def call(path, payload=None):\n"
        "    req = urllib.request.Request(BASE + path,\n"
        "        data=json.dumps(payload).encode() if payload is not None else None,\n"
        "        headers={'Content-Type': 'application/json'}, method='POST' if payload is not None else 'GET')\n"
        "    with urllib.request.urlopen(req, timeout=10) as r:\n"
        "        return r.status, r.read().decode()\n"
        "def test_health():\n"
        "    s, b = call('/api/health')\n"
        "    assert s == 200 and '\"ok\": true' in b\n"
        "def test_frontend_served():\n"
        "    with urllib.request.urlopen(BASE + '/', timeout=10) as r:\n"
        "        html = r.read().decode()\n"
        "    assert '<canvas' in html\n"
        "def test_notes_crud():\n"
        "    s, _ = call('/api/notes', {'name': 'n1', 'data': {}})\n"
        "    assert s == 200\n"
        "    s, b = call('/api/notes')\n"
        "    assert s == 200 and 'n1' in b\n"
    ),
    "requirements.txt": "pytest\n",
    ".env.example": "SECRET_KEY=change-me\nPORT=8000\n",
    "SETUP.md": "# Setup\n",
}


def _model_payload(files):
    import json as _j
    return {"output": [{"type": "message", "content": [{"type": "output_text", "text": _j.dumps({"files": files})}]}]}


def test_model_authored_build_verifies_end_to_end(tmp_path, monkeypatch):
    """The core claim, executed: model writes it, pipeline proves it."""
    from types import SimpleNamespace
    from app.builder import fullstack as fs
    from app.intelligence import meta_client as mc

    seen = {}

    class FakeClient:
        def __init__(self, *a, **k):
            self.config = SimpleNamespace(api_key="test-key",
                                          primary_model="muse-spark-1.3",
                                          advanced_model="muse-wonder-1.0",
                                          timeout_s=5)

        def respond(self, model, user_input, task="adhoc", **kw):
            seen["model"] = model
            return {"ok": True, "data": _model_payload(MODEL_APP_FILES),
                    "latency_ms": 9}

    monkeypatch.setattr(mc, "MetaClient", FakeClient)
    report = fs.build_fullstack("Build a tiny counter app with notes.",
                                tmp_path / "modelapp",
                                {"db": "sqlite", "payments": "none", "cache": "none"})
    assert report["verdict"] == "VERIFIED", report
    assert report.get("model_error", "") == ""
    assert report["author"].startswith("author: model muse-wonder-1.0"), report["author"]
    assert seen.get("model") == "muse-wonder-1.0"
    assert any(d["decision"].startswith("author: model") for d in report["decisions"])
    assert not any("MODEL GENERATION FAILED" in d["decision"] for d in report["decisions"])
    html = (tmp_path / "modelapp" / "frontend" / "index.html").read_text()
    assert "<canvas" in html
