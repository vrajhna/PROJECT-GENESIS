"""Dashboard, playground, terminal+approval, suggestions — all wired to real data."""

from fastapi.testclient import TestClient

from app.api import server as srv


def _client(tmp_path):
    srv.DATA_DIR = tmp_path / "data"
    srv.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return TestClient(srv.app)


def _login(c, tmp_path, monkeypatch, email="t@x.co"):
    import os
    from app.auth import accounts as acc
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/x")
    codes = {}
    monkeypatch.setattr(acc, "send_otp_mail",
                        lambda to, code, mailer=None: codes.__setitem__(to, code))
    assert c.post("/api/auth/request", json={"email": email}).status_code == 200
    r = c.post("/api/auth/verify",
               json={"email": email, "code": codes[email], "name": "Tester"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_dashboard_empty_then_populated(tmp_path, monkeypatch):
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/x")
    c = _client(tmp_path)
    d = c.get("/api/dashboard").json()
    assert d["ok"] is True and d["usage"]["projects"] == 0
    assert set(d["github"]) >= {"ok"}  # real state: True where gh/token exists
    h = _login(c, tmp_path, monkeypatch)
    pid = c.post("/api/projects", json={"name": "P"}, headers=h).json()["project"]["id"]
    d2 = c.get("/api/dashboard", headers=h).json()
    assert d2["usage"]["projects"] == 1
    assert d2["projects"][0]["id"] == pid
    assert d2["projects"][0]["verdict"] == "never-built"
    # a logged-out browser (no cookie jar) still sees nothing (privacy)
    from fastapi.testclient import TestClient as _TC
    from app.api import server as _srv
    assert _TC(_srv.app).get("/api/dashboard").json()["usage"]["projects"] == 0


def test_playground_runs_and_saves(tmp_path, monkeypatch):
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/x")
    c = _client(tmp_path)
    r = c.post("/api/playground/run", json={"code": "print(40 + 2)"}).json()
    assert r["ok"] is True and "42" in r["output"]
    assert "stdlib only" in r["note"]
    bad = c.post("/api/playground/run", json={"code": "raise SystemExit(3)"}).json()
    assert bad["ok"] is False and bad["exit_code"] == 3
    h = _login(c, tmp_path, monkeypatch, email="play@x.co")
    saved = c.post("/api/playground/run",
                   json={"code": "print('kept')", "save_as": "Kept"},
                   headers=h).json()
    assert saved["project"]["name"] == "Kept"
    assert c.get("/api/dashboard", headers=h).json()["usage"]["projects"] == 1


def test_terminal_approval_keeps_spaced_argv(tmp_path, monkeypatch):
    c = _client(tmp_path)
    h = _login(c, tmp_path, monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)  # laptop mode: terminal runs only locally
    pid = c.post("/api/projects", json={"name": "T"}, headers=h).json()["project"]["id"]
    c.post(f"/api/projects/{pid}/policy", json={"autopilot": False}, headers=h)
    req = c.post(f"/api/projects/{pid}/terminal",
                 json={"argv": ["echo", "hello world"]}, headers=h).json()
    yes = c.post(f"/api/projects/{pid}/terminal/approve",
                 json={"approval_id": req["approval_id"], "approved": True}, headers=h).json()
    assert yes["ok"] is True and "hello world" in yes["output"]


def test_terminal_approval_flow(tmp_path, monkeypatch):
    c = _client(tmp_path)
    h = _login(c, tmp_path, monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)  # laptop mode: terminal runs only locally
    pid = c.post("/api/projects", json={"name": "T"}, headers=h).json()["project"]["id"]
    c.post(f"/api/projects/{pid}/policy", json={"autopilot": False}, headers=h)
    req = c.post(f"/api/projects/{pid}/terminal", json={"argv": ["echo", "hi"]}, headers=h).json()
    assert req["ok"] is True
    for key in ("what", "why", "changes", "risks", "rollback"):
        assert key in req["explanation"], key
    assert req["options"] == ["approve", "reject"]
    no = c.post(f"/api/projects/{pid}/terminal/approve",
                json={"approval_id": req["approval_id"], "approved": False}, headers=h).json()
    assert no["ok"] is False
    req2 = c.post(f"/api/projects/{pid}/terminal", json={"argv": ["echo", "hi"]}, headers=h).json()
    yes = c.post(f"/api/projects/{pid}/terminal/approve",
                 json={"approval_id": req2["approval_id"], "approved": True}, headers=h).json()
    assert yes["ok"] is True and "hi" in yes["output"]
    bad = c.post(f"/api/projects/{pid}/terminal", json={"argv": "echo hi"}, headers=h)
    assert bad.status_code == 422  # string command rejected by schema: no shell, ever
    assert c.post(f"/api/projects/{pid}/terminal/approve",
                  json={"approval_id": "APR-9999", "approved": True}, headers=h).status_code == 400


def test_suggestions_on_real_signals(tmp_path, monkeypatch):
    c = _client(tmp_path)
    h = _login(c, tmp_path, monkeypatch, email="sug@x.co")
    pid = c.post("/api/projects", json={"name": "S"}, headers=h).json()["project"]["id"]
    empty = c.get(f"/api/projects/{pid}/suggestions", headers=h).json()
    assert any(s["title"] == "Empty project" for s in empty["suggestions"])
    work = srv.proj_dir(pid) / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / "leak.py").write_text('KEY = "sk-live-abcdefgh12345678"\n')
    (work / "note.py").write_text("# TODO: finish this\n")
    sugs = c.get(f"/api/projects/{pid}/suggestions", headers=h).json()["suggestions"]
    titles = [s["title"] for s in sugs]
    assert "No tests present" in titles
    assert "No setup docs" in titles
    assert any("TODO" in t for t in titles)
    assert "Possible secret in code" in titles
    (work / "test_note.py").write_text("def test_x():\n    assert True\n")
    (work / "README.md").write_text("# hi\n")
    (work / "leak.py").write_text("KEY = None\n")
    (work / "note.py").write_text("done\n")
    sugs2 = c.get(f"/api/projects/{pid}/suggestions").json()["suggestions"]
    assert any("collected" in t for t in [s["title"] for s in sugs2])
