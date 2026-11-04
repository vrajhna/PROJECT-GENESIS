"""Live parallel orchestration: run registry, SSE framing, streamed builds."""

import time

import pytest
from fastapi.testclient import TestClient


def test_registry_records_steps_in_order():
    from app.orchestrator import runs as runstore

    def fake_build(on_step=None):
        on_step({"step": "a", "ok": True})
        on_step({"step": "b", "ok": False})
        return {"verdict": "FAILED"}

    run_id = runstore.start_run("proj-1", "test", fake_build)
    assert run_id.startswith("run-")
    assert runstore.wait_done(run_id, timeout=10) is True
    snap = runstore.get_run(run_id)
    assert snap["status"] == "done"
    assert [s["step"] for s in snap["steps"]] == ["a", "b"]
    assert snap["report"]["verdict"] == "FAILED"


def test_registry_captures_crashes_as_failed():
    from app.orchestrator import runs as runstore

    def boom(on_step=None):
        on_step({"step": "x", "ok": True})
        raise RuntimeError("kablam")

    run_id = runstore.start_run("proj-2", "test", boom)
    assert runstore.wait_done(run_id, timeout=10) is True
    snap = runstore.get_run(run_id)
    assert snap["status"] == "failed"
    assert "kablam" in snap["error"]
    assert snap["steps"][0]["step"] == "x"


def test_unknown_run_is_none():
    from app.orchestrator import runs as runstore
    assert runstore.get_run("run-does-not-exist") is None
    assert runstore.wait_done("run-does-not-exist", timeout=1) is True


def _client(tmp_path):
    from app.api import server as srv
    srv.DATA_DIR = tmp_path / "data"
    srv.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return TestClient(srv.app)


def test_sse_frames_steps_and_done(tmp_path, monkeypatch):
    from app.api import server as srv
    from app.orchestrator import runs as runstore
    c = _client(tmp_path)
    canned = {
        "id": "run-x", "pid": "proj-x", "kind": "fullstack",
        "status": "done",
        "steps": [
            {"step": "install", "ok": True, "detail": "ok",
             "evidence": "", "lane": "live", "ts": 1.0},
            {"step": "review", "ok": True, "detail": "ok",
             "evidence": "", "lane": "review", "ts": 2.0},
        ],
        "report": {"verdict": "VERIFIED"}, "error": "", "started_at": 1,
    }
    monkeypatch.setattr(runstore, "get_run", lambda rid: canned if rid == "run-x" else None)
    r = c.get("/api/projects/proj-x/build/stream?run_id=run-x")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    body = r.text
    assert body.count("event: step") == 2
    assert '"lane": "live"' in body and '"lane": "review"' in body
    assert "event: done" in body and "VERIFIED" in body
    r2 = c.get("/api/projects/proj-x/build/stream?run_id=nope")
    assert r2.status_code == 404
    r3 = c.get("/api/projects/proj-x/build/status?run_id=run-x")
    assert r3.json()["run"]["status"] == "done"


def test_streamed_fullstack_build_verifies_live(tmp_path, monkeypatch):
    """End to end: stream=true returns immediately, status polls to a
    VERIFIED report with parallel lanes, report.json written."""
    from app.api import server as srv
    from app.auth import accounts as acc
    from app.builder import codegen as _cg
    # Deterministic: template author path (pipeline, lanes, Docker and
    # gates stay fully real; the live-model variant flakes under load).
    monkeypatch.setattr(_cg, "generate_with_model",
                        lambda *a, **k: {"ok": False,
                                         "error": "test: template path",
                                         "fallback": True})
    c = _client(tmp_path)
    import os
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@127.0.0.1:1/x")
    codes = {}
    monkeypatch.setattr(acc, "send_otp_mail",
                        lambda to, code, mailer=None: codes.__setitem__(to, code))
    email = "stream@x.co"
    assert c.post("/api/auth/request", json={"email": email}).status_code == 200
    token = c.post("/api/auth/verify",
                   json={"email": email, "code": codes[email], "name": "S"}).json()["token"]
    h = {"Authorization": "Bearer " + token}
    pid = c.post("/api/projects", json={"name": "Stream Demo"}, headers=h).json()["project"]["id"]
    c.post(f"/api/projects/{pid}/spec",
           json={"spec": "Users can register and log in. Users can create projects and tasks."}, headers=h)
    r = c.post(f"/api/projects/{pid}/fullstack?stream=true", json={}, headers=h)
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    deadline = time.time() + 420
    final = None
    while time.time() < deadline:
        s = c.get(f"/api/projects/{pid}/build/status",
                  params={"run_id": run_id}).json()
        assert s["ok"] is True
        if s["run"]["status"] in ("done", "failed"):
            final = s["run"]
            break
        time.sleep(3)
    assert final is not None, "run never finished"
    assert final["status"] == "done", final.get("error")
    assert final["report"]["verdict"] == "VERIFIED", final["report"]
    lanes = {s["step"]: s.get("lane") for s in final["report"]["steps"]}
    assert lanes.get("review") == "review"
    assert lanes.get("test") == "live"
    assert lanes.get("secure") == "secure"
    assert (srv.proj_dir(pid) / "report.json").exists()
