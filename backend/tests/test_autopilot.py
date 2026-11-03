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
