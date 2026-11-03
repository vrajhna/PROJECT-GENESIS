"""Settings: key paste + database choice, persisted to server .env."""

import os


def _client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.api import server as srv
    monkeypatch.setattr(srv, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(srv, "DATA_DIR", tmp_path / "data")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return TestClient(srv.app)


def test_key_paste_persists_without_echo(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/settings/key", json={"key": "test-key-123"}).json()
    assert r == {"ok": True, "key_configured": True}
    assert os.environ["MODEL_API_KEY"] == "test-key-123"
    assert "MODEL_API_KEY=test-key-123" in (tmp_path / ".env").read_text()
    r2 = c.post("/api/settings/key", json={"key": "rotated-456"}).json()
    assert r2["ok"] is True
    lines = (tmp_path / ".env").read_text().splitlines()
    assert sum(l.startswith("MODEL_API_KEY=") for l in lines) == 1
    assert c.post("/api/settings/key", json={"key": "x"}).status_code == 422


def test_database_choice_validates_and_persists(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/settings/database").json()["engine"] == "sqlite"
    bad = c.post("/api/settings/database", json={"engine": "postgres", "url": "nope"})
    assert bad.status_code == 400
    ok = c.post("/api/settings/database",
                json={"engine": "postgres", "url": "postgresql://u:p@h:5432/db"}).json()
    assert ok["engine"] == "postgres" and "pending" in ok["live"]
    refused = c.post("/api/settings/database",
                     json={"engine": "postgres",
                           "url": "postgresql://u:p@127.0.0.1:1/db"}).json()
    assert refused["ok"] is True and "unreachable" in refused["live"]
    assert os.environ["DATABASE_URL"].startswith("postgresql://")
    assert "DATABASE_URL=" in (tmp_path / ".env").read_text()
    back = c.post("/api/settings/database", json={"engine": "sqlite"}).json()
    assert back["engine"] == "sqlite"
    assert "DATABASE_URL" not in os.environ
