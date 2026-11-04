"""Server accounts (email OTP) + one-click publish. Files backend; pg skipped here."""

import re

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app.api import server as srv
    from app.auth import accounts as acc
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "gdata"))
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/x")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    srv.DATA_DIR = tmp_path / "gdata"
    codes = {}

    def fake_mailer(to, code, mailer=None):
        codes[to] = code

    orig_mailer = acc.send_otp_mail
    monkeypatch.setattr(acc, "send_otp_mail", fake_mailer)
    return TestClient(srv.app), codes, orig_mailer


def _join(c, codes, email, name="Tester"):
    r = c.post("/api/auth/request", json={"email": email})
    assert r.status_code == 200, r.text
    code = codes[email]
    assert re.fullmatch(r"\d{6}", code)
    r = c.post("/api/auth/verify", json={"email": email, "code": code})
    assert r.status_code == 400
    assert r.json().get("needProfile") is True
    r = c.post("/api/auth/verify",
               json={"email": email, "code": code, "name": name})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_request_validation_and_no_smtp(client, monkeypatch):
    from app.auth import accounts as acc
    c, _, orig = client
    assert c.post("/api/auth/request", json={"email": "nope"}).status_code == 400
    # real mailer + no SMTP in this env -> honest 503, nothing stored
    monkeypatch.setattr(acc, "send_otp_mail", orig)
    r = c.post("/api/auth/request", json={"email": "a@b.co"})
    assert r.status_code == 503


def test_full_login_lifecycle(client):
    c, codes, _ = client
    token = _join(c, codes, "me@x.co")
    r = c.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["member"]["email"] == "me@x.co"
    from fastapi.testclient import TestClient as _TC
    from app.api import server as _srv
    assert _TC(_srv.app).get("/api/me").status_code == 401
    assert c.get("/api/me", headers={"Authorization": "Bearer short"}).status_code == 401
    assert c.post("/api/auth/logout",
                  headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert c.get("/api/me",
                 headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_otp_is_secrets_backed():
    import inspect
    from app.auth import accounts as acc
    codes = {acc._new_otp() for _ in range(20)}
    assert len(codes) > 1
    assert all(re.fullmatch(r"\d{6}", c) for c in codes)
    src = inspect.getsource(acc._new_otp)
    assert "secrets" in src and "random" not in src


def test_wrong_code_and_try_limits(client):
    c, codes, _ = client
    c.post("/api/auth/request", json={"email": "w@x.co"})
    for _ in range(5):
        assert c.post("/api/auth/verify",
                      json={"email": "w@x.co", "code": "000000"}).status_code == 401
    # tries exhausted -> even the right code now fails
    r = c.post("/api/auth/verify",
               json={"email": "w@x.co", "code": codes["w@x.co"], "name": "W"})
    assert r.status_code == 401


def test_request_rate_limit(client):
    c, codes, _ = client
    for _ in range(5):
        assert c.post("/api/auth/request", json={"email": "r@x.co"}).status_code == 200
    assert c.post("/api/auth/request", json={"email": "r@x.co"}).status_code == 429


def test_project_owner_and_claim(client):
    c, codes, _ = client
    token = _join(c, codes, "owner@x.co", name="Owner")
    h = {"Authorization": f"Bearer {token}"}
    r = c.post("/api/projects", json={"name": "Mine"}, headers=h)
    pid = r.json()["project"]["id"]
    assert r.json()["project"]["owner_email"] == "owner@x.co"
    from app.api import server as _srv2
    legacy = "proj-legacy001"
    _srv2.save_project({"id": legacy, "name": "Legacy", "spec": "",
                        "created": 1, "policy": {"autopilot": True},
                        "owner_email": ""})
    assert c.get(f"/api/projects/{legacy}", headers=h).json()["project"]["owner_email"] == ""
    # claim legacy as owner
    assert c.post(f"/api/projects/{legacy}/claim", headers=h).status_code == 200
    # second user cannot claim it anymore
    token2 = _join(c, codes, "other@x.co", name="Other")
    r = c.post(f"/api/projects/{legacy}/claim",
               headers={"Authorization": f"Bearer {token2}"})
    assert r.status_code == 403


def _make_frontend(client, pid):
    from app.api import server as srv
    fe = srv.proj_dir(pid) / "work" / "frontend"
    fe.mkdir(parents=True)
    (fe / "index.html").write_text("<h1>hi</h1>")
    (fe / "app.js").write_text("console.log(1)")
    (fe / ".hidden").write_text("nope")


def test_publish_flow(client):
    c, codes, _ = client
    # login required
    assert c.post("/api/projects/nonexistent/publish", json={}).status_code == 401
    token = _join(c, codes, "pub@x.co", name="Pub")
    h = {"Authorization": f"Bearer {token}"}
    r = c.post("/api/projects", json={"name": "Shop"}, headers=h)
    pid = r.json()["project"]["id"]
    # nothing publishable yet
    r = c.post(f"/api/projects/{pid}/publish", json={}, headers=h)
    assert r.status_code == 400
    _make_frontend(c, pid)
    r = c.post(f"/api/projects/{pid}/publish", json={}, headers=h)
    assert r.status_code == 200, r.text
    slug = r.json()["slug"]
    url = r.json()["url"]
    assert url == f"/p/{slug}/"
    # served back, dotfiles excluded
    r = c.get(f"/p/{slug}/")
    assert r.status_code == 200 and "<h1>hi</h1>" in r.text
    assert c.get(f"/p/{slug}/app.js").status_code == 200
    assert c.get(f"/p/{slug}/.hidden").status_code == 404
    assert c.get("/p/../etc").status_code in (404, 307)
    # another member cannot touch it
    token2 = _join(c, codes, "intruder@x.co", name="Intruder")
    h2 = {"Authorization": f"Bearer {token2}"}
    assert c.post(f"/api/projects/{pid}/publish", json={},
                 headers=h2).status_code == 403
    # owner unpublishes
    assert c.delete(f"/api/projects/{pid}/publish", headers=h).status_code == 200
    assert c.get(f"/p/{slug}/").status_code == 404


def test_publish_claims_legacy_project(client):
    c, codes, _ = client
    from app.api import server as _srv
    pid = "proj-pubclaim1"
    _srv.save_project({"id": pid, "name": "Oldie", "spec": "",
                       "created": 1, "policy": {"autopilot": True},
                       "owner_email": ""})
    _make_frontend(c, pid)
    token = _join(c, codes, "first@x.co", name="First")
    h = {"Authorization": f"Bearer {token}"}
    assert c.post(f"/api/projects/{pid}/publish", json={}, headers=h).status_code == 200
    meta = c.get(f"/api/projects/{pid}").json()["project"]
    assert meta["owner_email"] == "first@x.co"


def test_listing_is_private_and_delete_works(client):
    c, codes, _ = client
    from fastapi.testclient import TestClient as _TC
    from app.api import server as _srv
    stranger = _TC(_srv.app)
    # logged out sees nothing
    assert stranger.get("/api/projects").json() == {"ok": True, "projects": []}
    assert stranger.get("/api/dashboard").json()["projects"] == []
    token_a = _join(c, codes, "alice@x.co", name="Alice")
    ha = {"Authorization": f"Bearer {token_a}"}
    pid_a = c.post("/api/projects", json={"name": "A"}, headers=ha).json()["project"]["id"]
    pid_legacy = "proj-legacy002"
    _srv.save_project({"id": pid_legacy, "name": "Legacy", "spec": "",
                       "created": 1, "policy": {"autopilot": True},
                       "owner_email": ""})
    token_b = _join(c, codes, "bob@x.co", name="Bob")
    hb = {"Authorization": f"Bearer {token_b}"}
    pid_b = c.post("/api/projects", json={"name": "B"}, headers=hb).json()["project"]["id"]
    # alice sees hers + the unclaimed legacy, never bob's
    ids = [p["id"] for p in c.get("/api/projects", headers=ha).json()["projects"]]
    assert pid_a in ids and pid_legacy in ids and pid_b not in ids
    dash = c.get("/api/dashboard", headers=ha).json()
    assert {p["id"] for p in dash["projects"]} == set(ids)
    # delete: logged out 401, stranger 403, unclaimed needs claim first
    assert stranger.delete(f"/api/projects/{pid_a}").status_code == 401
    assert c.delete(f"/api/projects/{pid_a}", headers=hb).status_code == 403
    assert c.delete(f"/api/projects/{pid_legacy}", headers=ha).status_code == 403
    c.post(f"/api/projects/{pid_legacy}/claim", headers=ha)
    # publish then delete removes the public copy too
    _make_frontend(c, pid_legacy)
    slug = c.post(f"/api/projects/{pid_legacy}/publish", json={}, headers=ha).json()["slug"]
    assert c.get(f"/p/{slug}/").status_code == 200
    assert c.delete(f"/api/projects/{pid_legacy}", headers=ha).json()["ok"] is True
    assert c.get(f"/p/{slug}/").status_code == 404
    assert c.get(f"/api/projects/{pid_legacy}").status_code == 404
    ids = [p["id"] for p in c.get("/api/projects", headers=ha).json()["projects"]]
    assert pid_a in ids and pid_legacy not in ids


CSRFH = {"X-Genesis-CSRF": "1", "Origin": "http://localhost:3101"}


def _authed_client(tmp_path, monkeypatch, email="c@x.co"):
    """TestClient with cookie-jar login (real OTP flow, fake mail). Returns
    (client, csrf_headers) — mutating calls need the CSRF headers, exactly
    like the real frontend sends."""
    from fastapi.testclient import TestClient
    from app.api import server as srv
    from app.auth import accounts as acc
    import os
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
               json={"email": email, "code": codes[email], "name": "Cookie"})
    assert r.status_code == 200, r.text
    assert "genesis_session" in r.headers.get("set-cookie", "")
    return c, CSRFH


def test_cookie_auth_and_logout(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.api import server as srv
    c, csrf = _authed_client(tmp_path, monkeypatch)
    # cookie alone authenticates (no Authorization header anywhere here)
    assert c.get("/api/me").json()["member"]["email"] == "c@x.co"
    assert c.post("/api/auth/logout", headers=csrf).status_code == 200
    assert c.get("/api/me").status_code == 401
    # a fresh browser (empty jar) is a stranger
    c2 = TestClient(srv.app)
    assert c2.get("/api/me").status_code == 401


def test_csrf_blocks_cookie_writes_without_proof(tmp_path, monkeypatch):
    c, csrf = _authed_client(tmp_path, monkeypatch, email="csrf@x.co")
    me = c.get("/api/me").json()["member"]
    assert me["email"] == "csrf@x.co"
    pid = c.post("/api/projects", json={"name": "CSRF"}, headers=csrf).json()["project"]["id"]
    # cookie is ambient but no CSRF header/origin -> 403, nothing happens
    r = c.post(f"/api/projects/{pid}/publish", json={})
    assert r.status_code == 403


def test_csrf_allows_with_header_and_origin(tmp_path, monkeypatch):
    c, csrf = _authed_client(tmp_path, monkeypatch, email="ok@x.co")
    me = c.get("/api/me").json()["member"]
    assert me["email"] == "ok@x.co"
    pid = c.post("/api/projects", json={"name": "CSRF2"}, headers=csrf).json()["project"]["id"]
    # cookie + header + allowed origin -> passes auth (400 = nothing to publish, not auth)
    r = c.post(f"/api/projects/{pid}/publish", json={},
               headers={"X-Genesis-CSRF": "1", "Origin": "http://localhost:3101"})
    assert r.status_code == 400
    # cookie + header + foreign origin -> 403
    r2 = c.post(f"/api/projects/{pid}/publish", json={},
                headers={"X-Genesis-CSRF": "1", "Origin": "https://evil.example"})
    assert r2.status_code == 403


def test_private_project_access(tmp_path, monkeypatch):
    c, csrf = _authed_client(tmp_path, monkeypatch, email="a@x.co")
    pid = c.post("/api/projects", json={"name": "Mine"}, headers=csrf).json()["project"]["id"]
    assert c.get(f"/api/projects/{pid}").status_code == 200
    from fastapi.testclient import TestClient
    from app.api import server as srv
    stranger = TestClient(srv.app)
    assert stranger.get(f"/api/projects/{pid}").status_code == 401


def test_local_mode_is_open_no_login_walls(tmp_path, monkeypatch):
    """Laptop/terminal mode (no DATABASE_URL): your files, your machine."""
    from fastapi.testclient import TestClient
    from app.api import server as srv
    monkeypatch.delenv("DATABASE_URL", raising=False)
    srv.DATA_DIR = tmp_path / "data"
    srv.DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = TestClient(srv.app)
    assert c.get("/api/health").json()["mode"] == "local"
    pid = c.post("/api/projects", json={"name": "Local"}).json()["project"]["id"]
    assert c.get(f"/api/projects/{pid}").json()["project"]["name"] == "Local"
    assert c.get("/api/projects").json()["projects"][0]["id"] == pid
    assert c.delete(f"/api/projects/{pid}").json()["ok"] is True


def test_stream_endpoints_require_login(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.api import server as srv
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/x")
    srv.DATA_DIR = tmp_path / "data"
    srv.DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = TestClient(srv.app)
    assert c.get("/api/projects/x/build/status?run_id=r").status_code == 401
    assert c.get("/api/projects/x/build/stream?run_id=r").status_code == 401


def test_health_mode_and_require_db(tmp_path, monkeypatch):
    import os
    from fastapi.testclient import TestClient
    from app.api import server as srv
    srv.DATA_DIR = tmp_path / "data"
    srv.DATA_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("GENESIS_REQUIRE_DB", raising=False)
    c = TestClient(srv.app)
    h = c.get("/api/health").json()
    assert h["ok"] is True and h["mode"] == "local"
    monkeypatch.setenv("GENESIS_REQUIRE_DB", "1")
    r = c.get("/api/health")
    assert r.status_code == 503
    assert "DATABASE_URL" in r.json()["error"]


def test_cookie_secure_on_production_host(client):
    c, codes, _ = client
    email = "prod@x.co"
    r = c.post("/api/auth/request", json={"email": email})
    assert r.status_code == 200, r.text
    r = c.post("/api/auth/verify",
               json={"email": email, "code": codes[email], "name": "Prod"},
               headers={"host": "genesis-api.webstudiobhiwadi.com"})
    assert r.status_code == 200, r.text
    sc = r.headers.get("set-cookie", "")
    assert "genesis_session=" in sc
    assert "; Secure" in sc and "samesite=none" in sc.lower().replace(" ", "")
    # local/test hosts must NOT force Secure (laptop mode over http)
    email2 = "loc@x.co"
    assert c.post("/api/auth/request", json={"email": email2}).status_code == 200
    r2 = c.post("/api/auth/verify",
                json={"email": email2, "code": codes[email2], "name": "Loc"})
    sc2 = r2.headers.get("set-cookie", "")
    assert "genesis_session=" in sc2 and "Secure" not in sc2
