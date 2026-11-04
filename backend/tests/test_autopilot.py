"""Autopilot: aggressive-by-default, guarded at the world boundary."""

import io
import zipfile

from app.api import server as srv


def _client(tmp_path):
    from fastapi.testclient import TestClient
    srv.DATA_DIR = tmp_path / "data"
    srv._gates.clear()
    return TestClient(srv.app)


def test_new_projects_start_in_autopilot(tmp_path):
    c = _client(tmp_path)
    meta = c.post("/api/projects", json={"name": "A"}).json()["project"]
    assert meta["policy"] == {"autopilot": True}
    got = c.get(f"/api/projects/{meta['id']}").json()["project"]
    assert got["policy"] == {"autopilot": True}


def test_policy_flip_persists(tmp_path):
    c = _client(tmp_path)
    pid = c.post("/api/projects", json={"name": "A"}).json()["project"]["id"]
    r = c.post(f"/api/projects/{pid}/policy", json={"autopilot": False}).json()
    assert r["ok"] and r["policy"] == {"autopilot": False}
    bad = c.post(f"/api/projects/{pid}/policy", json={})
    assert bad.status_code == 422  # house convention: schema errors are 422


def test_autopilot_runs_safe_commands_immediately(tmp_path):
    c = _client(tmp_path)
    pid = c.post("/api/projects", json={"name": "A"}).json()["project"]["id"]
    r = c.post(f"/api/projects/{pid}/terminal", json={"argv": ["echo", "hello"]}).json()
    assert "approval_id" not in r and r.get("autopilot") is True
    assert r["ok"] is True and "hello" in r["output"]


def test_autopilot_still_gates_push_like_commands(tmp_path):
    c = _client(tmp_path)
    pid = c.post("/api/projects", json={"name": "A"}).json()["project"]["id"]
    for argv in (["git", "push"], ["curl", "http://x"], ["rm", "-rf", "."]):
        r = c.post(f"/api/projects/{pid}/terminal", json={"argv": argv}).json()
        assert "approval_id" in r, argv


def test_manual_mode_asks_for_everything(tmp_path):
    c = _client(tmp_path)
    pid = c.post("/api/projects", json={"name": "A"}).json()["project"]["id"]
    c.post(f"/api/projects/{pid}/policy", json={"autopilot": False})
    r = c.post(f"/api/projects/{pid}/terminal", json={"argv": ["echo", "hi"]}).json()
    assert "approval_id" in r


def test_dotenv_loader_parses_and_never_overrides(tmp_path, monkeypatch):
    from app.api.server import _load_dotenv
    f = tmp_path / ".env"
    f.write_text('# comment\nMODEL_API_KEY=abc123\nEMPTY=\n')
    monkeypatch.setenv("MODEL_API_KEY", "real")
    assert _load_dotenv(f) == {"EMPTY": ""}  # real env never overridden, not reported
    import os
    assert os.environ["MODEL_API_KEY"] == "real"


def test_engine_zip_never_contains_dotenv(tmp_path):
    blob = _client(tmp_path).get("/api/download/engine").content
    names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
    assert not any(n.endswith("/.env") or n == ".env" for n in names)


def test_terminal_refused_in_server_mode(tmp_path, monkeypatch):
    from app.auth import accounts as acc
    c = _client(tmp_path)
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/x")
    codes = {}
    monkeypatch.setattr(acc, "send_otp_mail",
                        lambda to, code, mailer=None: codes.__setitem__(to, code))
    c.post("/api/auth/request", json={"email": "t@x.co"})
    token = c.post("/api/auth/verify",
                   json={"email": "t@x.co", "code": codes["t@x.co"],
                         "name": "T"}).json()["token"]
    h = {"Authorization": "Bearer " + token}
    pid = c.post("/api/projects", json={"name": "A"}, headers=h).json()["project"]["id"]
    r = c.post(f"/api/projects/{pid}/terminal", json={"argv": ["echo", "hi"]},
               headers=h)
    assert r.status_code == 403 and "laptop" in r.json()["error"]
    r = c.post(f"/api/projects/{pid}/terminal/approve",
               json={"approval_id": "x", "approved": True}, headers=h)
    assert r.status_code == 403


def test_terminal_children_never_see_server_secrets(tmp_path, monkeypatch):
    import sys
    monkeypatch.setenv("MODEL_API_KEY", "LLM_probe_secret")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    srv.DATA_DIR = tmp_path / "data"
    out = srv._exec_terminal(
        "probe-proj",
        [sys.executable, "-c",
         "import os;print('LEAK' if 'MODEL_API_KEY' in os.environ else 'clean')"])
    assert out["ok"] is True and out["output"].strip() == "clean"
