"""Pipeline + API: the core building ability, executed for real."""

import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.server import app
from app.builder.pipeline import build_and_verify

SPEC = "Users can register and log in securely. Users can create projects and tasks."


def test_pipeline_verifies_end_to_end(tmp_path: Path):
    report = build_and_verify(SPEC, tmp_path / "proj")
    assert report["verdict"] == "VERIFIED", report
    assert [s["step"] for s in report["steps"]] == [
        "understand", "plan", "generate", "install", "start",
        "test", "review", "logs", "retest"]
    assert all(s["ok"] for s in report["steps"])
    assert report["preview_url"].startswith("http://127.0.0.1:")
    assert (tmp_path / "proj" / ".venv").exists()


def test_pipeline_blocks_empty_spec(tmp_path: Path):
    report = build_and_verify("   ", tmp_path / "empty")
    assert report["verdict"] == "BLOCKED"


def _client(tmp_path: Path) -> TestClient:
    import app.api.server as srv
    srv.DATA_DIR = tmp_path / "data"
    srv.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return TestClient(app)


def test_api_health_and_request_id(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "data"))
    c = _client(tmp_path)
    r = c.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert r.headers.get("X-Request-ID", "").startswith("req-")


def test_api_project_flow_and_build(tmp_path: Path, monkeypatch):
    import os
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "data"))
    from app.auth import accounts as acc
    codes = {}
    monkeypatch.setattr(acc, "send_otp_mail",
                        lambda to, code, mailer=None: codes.__setitem__(to, code))
    c = _client(tmp_path)
    email = "flow@x.co"
    assert c.post("/api/auth/request", json={"email": email}).status_code == 200
    token = c.post("/api/auth/verify",
                   json={"email": email, "code": codes[email], "name": "Flow"}).json()["token"]
    h = {"Authorization": "Bearer " + token}
    pid = c.post("/api/projects", json={"name": "Demo"}, headers=h).json()["project"]["id"]
    assert c.get(f"/api/projects/{pid}").json()["project"]["name"] == "Demo"
    assert c.get("/api/projects", headers=h).json()["projects"][0]["id"] == pid
    spec = c.post(f"/api/projects/{pid}/spec", json={"spec": SPEC}).json()
    assert spec["ok"] is True and len(spec["requirements"]) == 2
    chat = c.post(f"/api/projects/{pid}/chat", json={"message": "also add search"}).json()
    assert chat["ok"] is True and chat["mode"] == "plan"
    short = c.post(f"/api/projects/{pid}/chat", json={"message": "hi"}).json()
    assert short["mode"] in ("plan", "clarify")
    build = c.post(f"/api/projects/{pid}/build", timeout=600).json()
    assert build["ok"] is True and build["report"]["verdict"] == "VERIFIED"
    assert c.get(f"/api/projects/{pid}/report").json()["ok"] is True
    tree = c.get(f"/api/projects/{pid}/tree").json()
    assert any("app_server.py" in f for f in tree["files"])
    content = c.get(f"/api/projects/{pid}/files", params={"path": "SPEC.json"}).json()
    assert "requirements" in content["content"]


def test_api_zip_upload_download(tmp_path: Path):
    c = _client(tmp_path)
    pid = c.post("/api/projects", json={"name": "Zip"}).json()["project"]["id"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("hello.py", "print(1)\n")
    r = c.post(f"/api/projects/{pid}/upload",
               files={"file": ("proj.zip", buf.getvalue(), "application/zip")})
    assert r.json()["ok"] is True
    bad = io.BytesIO()
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("../../evil.py", "x")
    r2 = c.post(f"/api/projects/{pid}/upload",
                files={"file": ("evil.zip", bad.getvalue(), "application/zip")})
    assert r2.json()["ok"] is False
    dl = c.get(f"/api/projects/{pid}/download")
    assert dl.status_code == 200 and dl.headers["content-type"] == "application/zip"


def test_api_github_honesty(tmp_path: Path):
    c = _client(tmp_path)
    st = c.get("/api/github/connect").json()
    assert set(st) >= {"ok"}
    if st["ok"]:
        assert st.get("login")
    else:
        assert "error" in st
    pid = c.post("/api/projects", json={"name": "Gh"}).json()["project"]["id"]
    r = c.post(f"/api/projects/{pid}/github/clone",
               json={"url": "https://example.com/o/r"})
    assert r.status_code == 400
