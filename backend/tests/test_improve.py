"""Improve-existing path: snapshots, existing-code context, restore."""

import json

from app.builder.files import collect_existing_context, snapshot_project


def _tree(base):
    (base / "app.py").write_text("print('mine')\n")
    (base / "data.txt").write_text("hello\n")
    (base / "pic.png").write_bytes(b"\x89PNG\r\n\x1a\nbinary-bytes")
    venv = base / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_text("x" * 100)
    (base / "__pycache__" / "a.pyc").parent.mkdir(parents=True, exist_ok=True)
    (base / "__pycache__" / "a.pyc").write_bytes(b"\x00" * 10)


def test_snapshot_saves_user_files_skips_junk(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    _tree(work)
    out = snapshot_project(work)
    assert out["files"] == 3, out
    snap = work / ".genesis" / "snapshots" / out["at"]
    assert (snap / "app.py").read_text() == "print('mine')\n"
    assert (snap / "data.txt").exists()
    assert (snap / "pic.png").exists()  # snapshots keep bytes; context skips them
    assert not (snap / ".venv").exists()
    assert not (snap / "__pycache__").exists()


def test_snapshot_empty_dir_skips(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    assert snapshot_project(work) == {"skipped": "nothing to snapshot"}


def test_collect_existing_context(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    assert collect_existing_context(work) == ""
    _tree(work)
    ctx = collect_existing_context(work)
    assert "--- app.py ---" in ctx and "print('mine')" in ctx
    assert "pic.png" not in ctx
    assert ".venv" not in ctx


def test_prompt_carries_existing_and_modify_instruction():
    from app.intelligence.prompt_manager import render
    _, prompt = render("codegen.fullstack", {
        "spec": "s", "requirements": "- R: x",
        "existing": "--- app.py ---\nprint('mine')\n"})
    assert "print('mine')" in prompt
    assert "MODIFY" in prompt or "modify" in prompt.lower()


def _payload(files):
    return {"output": [{"type": "message", "content": [{"type": "output_text",
             "text": json.dumps({"files": files})}]}]}


GOOD = {
    "frontend/index.html": "<html><body><canvas id='b'></canvas></body></html>",
    "frontend/app.js": "console.log(1);",
    "frontend/style.css": "body{}",
    "backend/server.py": "# stdlib\nBIND = (\"127.0.0.1\", 8000)\n",
    "tests/test_app.py": "def test_x():\n    assert True\n",
    "requirements.txt": "pytest\n",
}


class CaptureRouter:
    def __init__(self):
        from types import SimpleNamespace
        self.client = SimpleNamespace(config=SimpleNamespace(
            api_key="test-key", primary_model="muse-spark-1.3",
            advanced_model="muse-wonder-1.0", timeout_s=30))
        self.seen = ""

    def run(self, task_kind, user_input):
        self.seen = user_input
        return {"ok": True, "data": _payload(GOOD), "model": "muse-wonder-1.0",
                "latency_ms": 1, "task_kind": task_kind}


def test_generate_passes_existing_code_to_model():
    from app.builder import codegen
    router = CaptureRouter()
    out = codegen.generate_with_model("s", [], router=router,
                                      existing="--- app.py ---\nprint('mine')\n")
    assert out["ok"] is True
    assert "print('mine')" in router.seen


def _authed(tmp_path, monkeypatch, email="i@x.co"):
    from fastapi.testclient import TestClient
    from app.api import server as srv
    from app.auth import accounts as acc
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/x")
    srv.DATA_DIR = tmp_path / "data"
    srv.DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = TestClient(srv.app)
    codes = {}
    monkeypatch.setattr(acc, "send_otp_mail",
                        lambda to, code, mailer=None: codes.__setitem__(to, code))
    assert c.post("/api/auth/request", json={"email": email}).status_code == 200
    r = c.post("/api/auth/verify",
               json={"email": email, "code": codes[email], "name": "I"})
    token = r.json()["token"]
    pid = c.post("/api/projects", json={"name": "Imp"},
                 headers={"Authorization": "Bearer " + token}).json()["project"]["id"]
    return c, {"Authorization": "Bearer " + token}, pid


def test_snapshot_list_and_restore(tmp_path, monkeypatch):
    from app.api import server as srv
    c, h, pid = _authed(tmp_path, monkeypatch)
    work = srv.proj_dir(pid) / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / "notes.txt").write_text("v1\n")
    from app.builder.files import snapshot_project
    snap = snapshot_project(work)
    assert snap["files"] == 1
    (work / "notes.txt").write_text("v2 clobbered\n")
    r = c.get(f"/api/projects/{pid}/snapshots", headers=h)
    assert r.status_code == 200 and len(r.json()["snapshots"]) == 1
    ts = r.json()["snapshots"][0]["at"]
    r = c.post(f"/api/projects/{pid}/snapshots/{ts}/restore", headers=h)
    assert r.json() == {"ok": True, "restored": 1, "at": ts}
    assert (work / "notes.txt").read_text() == "v1\n"


def test_restore_authz_and_validation(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.api import server as srv
    c, h, pid = _authed(tmp_path, monkeypatch, email="own@x.co")
    stranger = TestClient(srv.app)
    assert stranger.post(f"/api/projects/{pid}/snapshots/x/restore").status_code == 401
    c2, h2 = _authed(tmp_path, monkeypatch, email="str@x.co")[:2]
    assert c2.post(f"/api/projects/{pid}/snapshots/x/restore", headers=h2).status_code == 403
    assert c.post(f"/api/projects/{pid}/snapshots/nope/restore", headers=h).status_code == 400
    assert c.post(f"/api/projects/{pid}/snapshots/../x/restore", headers=h).status_code in (400, 404)
    assert c.get(f"/api/projects/{pid}/snapshots", headers=h).json() == {"ok": True, "snapshots": []}
