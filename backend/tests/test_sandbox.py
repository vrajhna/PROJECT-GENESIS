"""Docker sandbox: untrusted generated apps run isolated (Part III)."""

import os
from pathlib import Path

from app.sandbox.docker_runner import (app_container_argv, describe,
                                       docker_available, sandbox_mode)


def test_container_argv_is_hardened(tmp_path: Path):
    argv = app_container_argv(tmp_path, "backend/server.py", "genesis-app-x", 8123)
    joined = " ".join(argv)
    assert argv[0] == "docker" and "run" in argv
    assert "--user" in argv and "1000:1000" in argv          # non-root
    assert "--memory" in argv and "512m" in argv             # resource limits
    assert "--cpus" in argv and "--pids-limit" in argv
    assert "--cap-drop" in argv and "ALL" in argv
    assert "--security-opt" in argv and "no-new-privileges" in argv
    assert "--read-only" in argv                             # rootfs immutable
    assert "127.0.0.1:8123:8000" in argv                     # localhost-only publish
    assert "GENESIS_BIND=0.0.0.0" in argv                     # containers listen inside, stay loopback outside
    assert "python:3.12-slim" in argv
    assert argv[-4:] == ["python", "backend/server.py", "--port", "8000"]
    assert "0.0.0.0:8123" not in joined and " -p 0.0.0.0" not in joined  # never world-published


def test_mode_selection_is_honest(monkeypatch):
    monkeypatch.setenv("GENESIS_SANDBOX", "venv")
    assert sandbox_mode() == "venv"
    monkeypatch.setenv("GENESIS_SANDBOX", "docker")
    assert sandbox_mode() == ("docker" if docker_available() else "venv")
    assert isinstance(docker_available(), bool)
    assert describe().startswith(("docker:", "venv (host process"))


def test_build_runs_app_in_docker_when_available(tmp_path: Path, monkeypatch):
    if not docker_available():
        import pytest
        pytest.skip("docker daemon or image unavailable on this machine")
    monkeypatch.setenv("GENESIS_SANDBOX", "docker")
    from app.builder.fullstack import build_fullstack
    report = build_fullstack("Build me a blog where I can publish posts. "
                             "No login needed.", tmp_path / "blog")
    assert report["verdict"] == "VERIFIED", report
    assert report["sandbox"].startswith("docker:python:3.12-slim")
    assert "non-root" in report["sandbox"]


def test_build_venv_mode_is_labeled(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GENESIS_SANDBOX", "venv")
    from app.builder.pipeline import build_and_verify
    report = build_and_verify("Build me a task list app.",
                              tmp_path / "tasks", timeout_s=300)
    assert report["verdict"] == "VERIFIED", report
    assert report["sandbox"].startswith("venv (host process")
