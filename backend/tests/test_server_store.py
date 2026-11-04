"""Website strict persistence: Postgres only, never file fallback.

SQL shapes live in test_pg_store.py. These tests prove routing:
strict mode uses pg helpers, an unreachable store answers 503, chat
surfaces model failures, and laptop mode is untouched (covered elsewhere).
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def strict_env(tmp_path, monkeypatch):
    from app.api import server as srv
    monkeypatch.setenv("GENESIS_REQUIRE_DB", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/x")
    srv.DATA_DIR = tmp_path / "data"
    srv.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return srv


def test_strict_unavailable_answers_503(strict_env, monkeypatch):
    from app.db import pg
    monkeypatch.setattr(pg, "available", lambda: False)
    c = TestClient(strict_env.app)
    r = c.get("/api/projects")
    assert r.status_code == 503
    assert "file fallback" in r.json()["error"]
    assert c.get("/api/health").status_code == 503


def test_strict_project_report_use_postgres(strict_env, monkeypatch):
    from app.db import pg
    store = {}

    class Conn:
        def close(self):
            pass

    monkeypatch.setattr(pg, "available", lambda: True)
    monkeypatch.setattr(pg, "connect", lambda: Conn())
    monkeypatch.setattr(pg, "project_save",
                        lambda con, meta: store.setdefault(
                            "project:" + meta["id"], dict(meta)))
    monkeypatch.setattr(pg, "project_get",
                        lambda con, pid: store.get("project:" + pid))
    monkeypatch.setattr(pg, "report_save",
                        lambda con, pid, rep: store.__setitem__(
                            "report:" + pid, dict(rep)))
    monkeypatch.setattr(pg, "report_get",
                        lambda con, pid: store.get("report:" + pid))
    srv = strict_env
    assert srv.strict_db() is True
    srv.save_project({"id": "proj-x", "name": "X", "spec": "",
                      "created": 1, "policy": {}, "owner_email": ""})
    assert srv.load_project("proj-x")["name"] == "X"
    srv.save_report("proj-x", {"verdict": "VERIFIED"})
    assert srv.load_report("proj-x")["verdict"] == "VERIFIED"
    assert not (srv.DATA_DIR / "projects").exists()


def test_strict_auth_refuses_file_fallback(strict_env, monkeypatch):
    from app.auth import accounts as acc
    from app.db import pg
    monkeypatch.setattr(pg, "connect", lambda: None)
    with pytest.raises(acc.AuthFail) as exc:
        acc.request_otp("a@b.co", mailer=lambda to, code: None)
    assert exc.value.status == 503
    assert not list((strict_env.DATA_DIR / "accounts").glob("*"))


def test_strict_database_settings(tmp_path, monkeypatch):
    import os
    from app.api import server as srv
    monkeypatch.setattr(srv, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(srv, "DATA_DIR", tmp_path / "data")
    monkeypatch.setenv("GENESIS_REQUIRE_DB", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    c = TestClient(srv.app)
    assert c.post("/api/settings/database",
                  json={"engine": "sqlite"}).status_code == 400
    bad = c.post("/api/settings/database",
                 json={"engine": "postgres",
                       "url": "postgresql://u:p@127.0.0.1:1/db"})
    assert bad.status_code == 400
    assert "DATABASE_URL" not in os.environ


def test_chat_surfaces_model_failure(tmp_path, monkeypatch):
    from app.api import server as srv
    from app.intelligence import model_router as mr
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("GENESIS_REQUIRE_DB", raising=False)
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    srv.DATA_DIR = tmp_path / "data"
    srv.DATA_DIR.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(mr.ModelRouter, "run",
                        lambda self, kind, prompt: {
                            "ok": False, "error": "HTTP 503 overloaded"})
    c = TestClient(srv.app)
    pid = c.post("/api/projects", json={"name": "C"}).json()["project"]["id"]
    c.post(f"/api/projects/{pid}/spec",
           json={"spec": "Users can log in. Users manage tasks."})
    r = c.post(f"/api/projects/{pid}/chat",
               json={"message": "also add search please"}).json()
    assert r["mode"] == "plan"
    assert "503" in r["model_error"]


def test_runs_persist_snapshots_in_strict_mode(monkeypatch):
    from app.db import pg
    from app.orchestrator import runs as runstore
    saved = []

    class Conn:
        def close(self):
            pass

    monkeypatch.setenv("GENESIS_REQUIRE_DB", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setattr(pg, "available", lambda: True)
    monkeypatch.setattr(pg, "connect", lambda: Conn())
    monkeypatch.setattr(pg, "run_save",
                        lambda con, snap: saved.append(dict(snap)))
    rid = runstore.start_run("proj-1", "test",
                             lambda on_step=None: {"verdict": "OK"})
    assert runstore.wait_done(rid, timeout=10) is True
    assert saved and saved[-1]["status"] == "done"
    assert saved[-1]["id"] == rid


def test_get_run_falls_back_to_postgres(monkeypatch):
    from app.db import pg
    from app.orchestrator import runs as runstore

    class Conn:
        def close(self):
            pass

    monkeypatch.setenv("GENESIS_REQUIRE_DB", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setattr(pg, "available", lambda: True)
    monkeypatch.setattr(pg, "connect", lambda: Conn())
    monkeypatch.setattr(pg, "run_get", lambda con, rid: {
        "id": rid, "pid": "proj-9", "kind": "fullstack",
        "status": "done", "steps": [{"step": "test", "ok": True}],
        "report": {"verdict": "VERIFIED"}, "error": "", "started_at": 1})
    snap = runstore.get_run("run-db-fallback-1")
    assert snap["status"] == "done"
    assert snap["report"]["verdict"] == "VERIFIED"
