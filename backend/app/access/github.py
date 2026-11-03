"""GitHub workflows: honest about what is and isn't connected.

Genuinely works without any account:
  public (or file://) clone, branch listing/creation, diff summaries,
  test-before-change via TestingAgent.
Pushing requires BOTH an approved approval item AND a token in the
GITHUB_TOKEN env var. Private-repo OAuth connect is NOT implemented —
requesting it returns an explicit 'not supported' instead of pretending.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from ..agents.roles import TestingAgent

REMOTE_RE = re.compile(
    r"^(?:https://github\.com/|git@github\.com:)(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$")


def parse_repo_url(url: str) -> dict:
    m = REMOTE_RE.match(url.strip())
    if not m:
        if url.startswith("file://"):
            return {"kind": "local", "owner": "", "repo": url}
        return {"ok": False, "error": "only github.com HTTPS/SSH or file:// URLs are supported"}
    return {"ok": True, "kind": "github", **m.groupdict()}


def _git(repo: Path, *args: str, timeout_s: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                          text=True, timeout=timeout_s, shell=False)


def clone(url: str, dest: Path, branch: str | None = None) -> dict:
    parsed = parse_repo_url(url)
    if not parsed.get("ok", True) and parsed.get("kind") != "local":
        return parsed
    if dest.exists() and any(dest.iterdir()):
        return {"ok": False, "error": "destination is not empty (refusing to overwrite)"}
    dest.mkdir(parents=True, exist_ok=True)
    cmd = ["clone", "--depth", "50", url, str(dest)]
    if branch:
        cmd = ["clone", "--depth", "50", "--branch", branch, url, str(dest)]
    proc = subprocess.run(["git", *cmd], capture_output=True, text=True,
                          timeout=300, shell=False)
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip()[-500:]}
    _git(dest, "config", "user.email", "genesis@local")
    _git(dest, "config", "user.name", "genesis")
    return {"ok": True, "summary": f"cloned into {dest}"}


def list_branches(repo: Path) -> dict:
    proc = _git(repo, "branch", "-a", "--format=%(refname:short)")
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip()[-300:]}
    branches = sorted({b.strip().removeprefix("origin/") for b in proc.stdout.splitlines()
                       if b.strip() and "HEAD" not in b})
    cur = _git(repo, "branch", "--show-current")
    return {"ok": True, "current": cur.stdout.strip(), "branches": branches}


def create_branch(repo: Path, name: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,99}", name):
        return {"ok": False, "error": "invalid branch name"}
    proc = _git(repo, "checkout", "-b", name)
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip()[-300:]}
    return {"ok": True, "summary": f"on branch {name}"}


def diff_summary(repo: Path, base: str = "HEAD") -> dict:
    stat = _git(repo, "diff", "--stat", base)
    names = _git(repo, "diff", "--name-only", base)
    if stat.returncode != 0:
        return {"ok": False, "error": stat.stderr.strip()[-300:]}
    files = [f for f in names.stdout.splitlines() if f.strip()]
    return {"ok": True, "files": files, "stat": stat.stdout.strip()[-2000:],
            "summary": f"{len(files)} file(s) changed vs {base}"}


def run_tests_first(repo: Path) -> dict:
    res = TestingAgent().run(repo)
    return {"ok": res.ok, "summary": res.summary, "failed_tests": res.data.get("failed_tests", [])}


def push(repo: Path, branch: str, approved: bool = False) -> dict:
    """Push only with explicit approval AND a token. Never silent."""
    if not approved:
        return {"ok": False, "error": "push requires an approved approval item"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"ok": False, "error": "GITHUB_TOKEN is not set; cannot push"}
    proc = _git(repo, "push", "origin", branch)
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip()[-500:]}
    return {"ok": True, "summary": f"pushed {branch}"}


def connect_account() -> dict:
    """Real connection state: gh CLI auth first, then GITHUB_TOKEN, else honest no.

    Never returns token material — login name only."""
    import subprocess
    try:
        proc = subprocess.run(["gh", "auth", "status"], capture_output=True,
                              text=True, timeout=15)
        if proc.returncode == 0:
            user = subprocess.run(["gh", "api", "user", "--jq", ".login"],
                                  capture_output=True, text=True, timeout=15)
            login = user.stdout.strip() or "unknown"
            return {"ok": True, "login": login, "via": "gh CLI"}
    except (FileNotFoundError, OSError):
        pass
    import os
    if os.environ.get("GITHUB_TOKEN"):
        return {"ok": True, "login": "token", "via": "GITHUB_TOKEN"}
    return {"ok": False,
            "error": "GitHub OAuth connect is not implemented. Public repos work "
                     "without an account; private repos and pushing need a token "
                     "set as GITHUB_TOKEN by the repo owner."}
