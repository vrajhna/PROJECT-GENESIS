"""Git checkpoints inside an explicit repo dir. Stdlib subprocess only.

`restore_checkpoint` is destructive (`git reset --hard`) and must sit
behind the approval gate. All commands run with `shell=False` and a timeout.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo: Path, *args: str, timeout_s: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        shell=False,
    )


def init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    proc = _git(repo, "init", "-q")
    if proc.returncode != 0:
        raise RuntimeError(f"git init failed: {proc.stderr.strip()}")
    _git(repo, "config", "user.email", "genesis@local")
    _git(repo, "config", "user.name", "genesis")


def create_checkpoint(repo: Path, message: str) -> str:
    add = _git(repo, "add", "-A")
    if add.returncode != 0:
        raise RuntimeError(f"git add failed: {add.stderr.strip()}")
    commit = _git(repo, "commit", "-q", "-m", message)
    if commit.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit.stderr.strip()}")
    rev = _git(repo, "rev-parse", "HEAD")
    if rev.returncode != 0:
        raise RuntimeError(f"git rev-parse failed: {rev.stderr.strip()}")
    return rev.stdout.strip()


def restore_checkpoint(repo: Path, sha: str) -> None:
    proc = _git(repo, "reset", "--hard", "-q", sha)
    if proc.returncode != 0:
        raise RuntimeError(f"git reset failed: {proc.stderr.strip()}")
