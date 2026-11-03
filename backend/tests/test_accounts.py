"""Server accounts (email OTP) + one-click publish. Files backend; pg skipped here."""

import re

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app.api import server as srv
    from app.auth import accounts as acc
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "gdata"))
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
    assert c.get("/api/me").status_code == 401
    assert c.get("/api/me", headers={"Authorization": "Bearer short"}).status_code == 401
    assert c.post("/api/auth/logout",
                  headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert c.get("/api/me",
                 headers={"Authorization": f"Bearer {token}"}).status_code == 401


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
    r = c.post("/api/projects", json={"name": "Legacy"})
    legacy = r.json()["project"]["id"]
    assert r.json()["project"]["owner_email"] == ""
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
    r = c.post("/api/projects", json={"name": "Oldie"})
    pid = r.json()["project"]["id"]
    _make_frontend(c, pid)
    token = _join(c, codes, "first@x.co", name="First")
    h = {"Authorization": f"Bearer {token}"}
    assert c.post(f"/api/projects/{pid}/publish", json={}, headers=h).status_code == 200
    meta = c.get(f"/api/projects/{pid}").json()["project"]
    assert meta["owner_email"] == "first@x.co"
