"""Access workflows: ZIP in/out, GitHub clone/branch/diff/push gates."""

import io
import subprocess
import zipfile
from pathlib import Path

from app.access import github as gh
from app.access.zips import inspect_tree, make_zip, safe_extract


def test_zip_roundtrip_and_inspect(tmp_path: Path):
    src = tmp_path / "proj"
    (src / "sub").mkdir(parents=True)
    (src / "a.py").write_text("print('hi')\n")
    (src / "sub" / "b.txt").write_text("hello\n")
    blob = make_zip(src)
    dest = tmp_path / "out"
    names = safe_extract(blob, dest)
    assert "a.py" in names and "sub/b.txt" in names
    assert (dest / "a.py").read_text() == "print('hi')\n"
    assert "SETUP.md" in [p for p in names]
    assert any("a.py" in f for f in inspect_tree(dest))


def test_make_zip_never_follows_symlinks(tmp_path: Path):
    src = tmp_path / "proj"
    src.mkdir()
    (src / "ok.py").write_text("print('hi')\n")
    outside = tmp_path / "secret.txt"
    outside.write_text("server-local secret\n")
    (src / "leak.py").symlink_to(outside)
    names = zipfile.ZipFile(io.BytesIO(make_zip(src))).namelist()
    assert "ok.py" in names and "leak.py" not in names
    assert "server-local secret" not in str(names)


def test_rate_limiter_blocks_bursts_but_not_neighbors():
    from app.api.server import _RateLimiter
    rl = _RateLimiter(per_minute=3)
    assert [rl.allowed("1.2.3.4") for _ in range(3)] == [True, True, True]
    assert rl.allowed("1.2.3.4") is False
    assert rl.allowed("5.6.7.8") is True


def test_pid_traversal_rejected(tmp_path):
    from fastapi.testclient import TestClient
    from app.api import server as srv
    srv.DATA_DIR = tmp_path / "data"
    c = TestClient(srv.app)
    for r in (c.get("/api/projects/../report"),
              c.get("/api/runs/../events"),
              c.get("/api/projects/../tree"),
              c.post("/api/projects/../terminal", json={"argv": ["echo", "hi"]})):
        assert r.status_code == 404, (r.status_code, r.text[:200])
    import pytest
    with pytest.raises(ValueError):
        srv.proj_dir("..")
    assert srv.load_project("..") is None


def test_zip_slip_and_bombs_rejected(tmp_path: Path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil.py", "x")
    try:
        safe_extract(buf.getvalue(), tmp_path / "d1")
    except ValueError as e:
        assert "escape" in str(e)
    else:
        raise AssertionError("zip-slip must be rejected")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i in range(5):
            zf.writestr(f"/abs{i}.py", "x")
    try:
        safe_extract(buf.getvalue(), tmp_path / "d2")
    except ValueError:
        pass
    else:
        raise AssertionError("absolute paths must be rejected")


def _local_repo(tmp_path: Path, name: str) -> Path:
    origin = tmp_path / name
    origin.mkdir()
    subprocess.run(["git", "init", "-q", str(origin)], check=True)
    subprocess.run(["git", "-C", str(origin), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(origin), "config", "user.name", "t"], check=True)
    (origin / "app.py").write_text("X = 1\n")
    (origin / "test_app.py").write_text("from app import X\n\ndef test_x():\n    assert X == 1\n")
    subprocess.run(["git", "-C", str(origin), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(origin), "commit", "-qm", "init"], check=True)
    return origin


def test_github_clone_branch_diff_tests(tmp_path: Path):
    origin = _local_repo(tmp_path, "origin")
    work = tmp_path / "work"
    res = gh.clone(f"file://{origin}", work)
    assert res["ok"] is True, res
    branches = gh.list_branches(work)
    assert branches["ok"] is True and branches["current"] in ("main", "master")
    assert gh.create_branch(work, "genesis/change-1")["ok"] is True
    assert gh.create_branch(work, "bad name!")["ok"] is False
    (work / "app.py").write_text("X = 2\n")
    diff = gh.diff_summary(work)
    assert diff["ok"] is True and diff["files"] == ["app.py"]
    assert "1 file(s) changed" in diff["summary"]
    tests = gh.run_tests_first(work)
    assert tests["ok"] is False  # X changed to 2, test expects 1
    assert any("test_x" in f for f in tests["failed_tests"])


def test_push_needs_approval_and_token(tmp_path: Path):
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    work = tmp_path / "w"
    assert gh.clone(f"file://{bare}", work)["ok"] is True
    (work / "f.txt").write_text("hi\n")
    subprocess.run(["git", "-C", str(work), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-qm", "x"], check=True)
    br = subprocess.run(["git", "-C", str(work), "branch", "--show-current"],
                        capture_output=True, text=True).stdout.strip()
    refused = gh.push(work, br, approved=False)
    assert refused["ok"] is False and "approval" in refused["error"]
    refused2 = gh.push(work, br, approved=True)
    assert refused2["ok"] is False and "GITHUB_TOKEN" in refused2["error"]


def test_connect_and_parse_are_honest():
    st = gh.connect_account()
    assert set(st) >= {"ok"}
    if st["ok"]:
        assert st.get("login")
    else:
        assert "error" in st
    parsed = gh.parse_repo_url("https://github.com/o/r")
    assert parsed["kind"] == "github" and parsed["owner"] == "o" and parsed["repo"] == "r"
    assert gh.parse_repo_url("https://example.com/o/r")["ok"] is False
    assert gh.clone("https://example.com/o/r", Path("/tmp/genesis-never"))["ok"] is False
