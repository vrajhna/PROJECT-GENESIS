"""Message 3: real full-stack generation, different specs, different apps."""

from pathlib import Path

from app.builder.fullstack import build_fullstack, detect_features, detect_resources

STORE_SPEC = ("Build me an online clothing store with products, a cart and checkout. "
              "Users must register and log in to buy.")
BLOG_SPEC = ("Build me a blog where I can publish posts and readers can comment. "
             "No login needed.")


def test_detector_picks_modules_per_idea():
    from app.agents.roles import ArchitectAgent
    arch = ArchitectAgent().run(STORE_SPEC)
    feats = detect_features(arch.data["requirements"])
    assert feats["auth"] is True and feats["cart"] is True
    res = detect_resources(arch.data["requirements"], feats)
    assert "product" in res and "order" in res
    arch2 = ArchitectAgent().run(BLOG_SPEC)
    feats2 = detect_features(arch2.data["requirements"])
    assert feats2["auth"] is False
    res2 = detect_resources(arch2.data["requirements"], feats2)
    assert len(res2) >= 1


def test_store_builds_verifies_and_persists(tmp_path: Path):
    report = build_fullstack(STORE_SPEC, tmp_path / "store")
    assert report["verdict"] == "VERIFIED", report
    assert any("auth" in d["decision"].lower() for d in report["decisions"])
    work = tmp_path / "store"
    for f in ("frontend/index.html", "frontend/app.js", "frontend/style.css",
              "backend/server.py", "backend/schema.sql", "tests/test_app.py",
              "SETUP.md", ".env.example", "backend/app.db"):
        assert (work / f).exists(), f
    assert report["preview_url"].startswith("http://127.0.0.1:")
    assert all(s["ok"] for s in report["steps"])


def test_blog_builds_without_auth(tmp_path: Path):
    report = build_fullstack(BLOG_SPEC, tmp_path / "blog")
    assert report["verdict"] == "VERIFIED", report
    assert any("No auth module" in d["decision"] for d in report["decisions"])
    assert (tmp_path / "blog" / "backend" / "app.db").exists()


def test_fullstack_blocks_empty_spec(tmp_path: Path):
    report = build_fullstack("   ", tmp_path / "empty")
    assert report["verdict"] == "BLOCKED"


GAME_SPEC = "Build me a playable snake game with a high-score board."


def test_game_builds_with_canvas_and_scores(tmp_path: Path):
    report = build_fullstack(GAME_SPEC, tmp_path / "game")
    assert report["verdict"] == "VERIFIED", report
    assert report["game"] is True
    html = (tmp_path / "game" / "frontend" / "index.html").read_text()
    js = (tmp_path / "game" / "frontend" / "app.js").read_text()
    assert "<canvas" in html and "/api/scores" in js
    assert any("game mode" in d["decision"] for d in report["decisions"])


def test_fullstack_api_end_to_end(tmp_path):
    from fastapi.testclient import TestClient
    from app.api import server as srv
    srv.DATA_DIR = tmp_path / "data"
    c = TestClient(srv.app)
    pid = c.post("/api/projects", json={"name": "Shop"}).json()["project"]["id"]
    c.post(f"/api/projects/{pid}/spec", json={"spec": STORE_SPEC})
    res = c.post(f"/api/projects/{pid}/fullstack", timeout=600).json()
    assert res["ok"] is True and res["report"]["verdict"] == "VERIFIED"
    assert any("auth" in d["decision"].lower() for d in res["report"]["decisions"])
