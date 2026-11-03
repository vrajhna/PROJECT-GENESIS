"""Message 3 hardening: progressive choices, transient-only retry, secure gate."""

import pytest

from app.builder.fullstack import (_is_transient, _secure_scan, decide_stack,
                                   detect_features, plan_questions, resolve_answers)
from app.agents.roles import ArchitectAgent

STORE = ("Build me an online clothing store with products, a cart and checkout. "
         "Users must register and log in to buy.")
BLOG = "Build me a blog where I can publish posts and readers can comment. No login needed."


def _reqs(spec):
    return ArchitectAgent().run(spec).data["requirements"]


def test_answers_default_and_reject():
    assert resolve_answers(None) == {"db": "sqlite", "cache": "none", "payments": "none"}
    assert resolve_answers({"db": "postgres"})["db"] == "postgres"
    with pytest.raises(ValueError):
        resolve_answers({"db": "oracle"})


def test_questions_progressive_not_upfront():
    reqs, feats = _reqs(STORE), detect_features(_reqs(STORE))
    ids = [q["id"] for q in plan_questions(reqs, feats)]
    assert ids[0] == "db"
    assert "payments" in ids  # selling in spec -> asked
    assert "cache" not in ids  # no scale talk -> not asked
    blog_ids = [q["id"] for q in plan_questions(_reqs(BLOG), detect_features(_reqs(BLOG)))]
    assert blog_ids == ["db"]  # simplest idea -> single question
    assert all(q["recommended"] for q in plan_questions(reqs, feats))


def test_stack_follows_answers():
    reqs, feats, res = _reqs(STORE), detect_features(_reqs(STORE)), ["product", "order"]
    default = decide_stack(reqs, feats, res, resolve_answers(None))
    assert any("SQLite" in d["decision"] for d in default)
    pg = decide_stack(reqs, feats, res, resolve_answers({"db": "postgres"}))
    assert any("PostgreSQL" in d["decision"] for d in pg)
    pay = decide_stack(reqs, feats, res, resolve_answers({"payments": "stripe-test"}))
    assert any("stripe-test" in d["decision"] and "test mode" in d["decision"].lower() for d in pay)


def test_retry_only_transient():
    assert _is_transient("pip install timed out after 240s")
    assert _is_transient("timeout waiting for health check")
    assert _is_transient("connection refused")
    assert not _is_transient("tests failed: FAILED tests/test_app.py::test_x")
    assert not _is_transient("security gate: unexpected runtime dependencies")


def test_secure_scan_blocks_bad_tree(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / "backend" / "server.py").write_text('ThreadingHTTPServer(("0.0.0.0", p), H)')
    (tmp_path / "frontend" / "app.js").write_text("fetch(x)")
    (tmp_path / ".env.example").write_text("SECRET_KEY=change-me\n")
    (tmp_path / "requirements.txt").write_text("pytest\nsk_live_abc=1\n")
    findings = _secure_scan(tmp_path, {"payments": "none"})
    assert any("127.0.0.1" in f for f in findings)
    assert any("live secret" in f for f in findings)


def test_questions_api_and_bad_answers_rejected(tmp_path):
    from fastapi.testclient import TestClient
    from app.api import server as srv
    srv.DATA_DIR = tmp_path / "data"
    c = TestClient(srv.app)
    pid = c.post("/api/projects", json={"name": "Q"}).json()["project"]["id"]
    assert c.get(f"/api/projects/{pid}/questions").status_code == 400  # no spec yet
    c.post(f"/api/projects/{pid}/spec", json={"spec": STORE})
    q = c.get(f"/api/projects/{pid}/questions").json()
    assert q["ok"] and q["questions"][0]["id"] == "db"
    bad = c.post(f"/api/projects/{pid}/fullstack", json={"answers": {"db": "oracle"}})
    assert bad.status_code == 400
