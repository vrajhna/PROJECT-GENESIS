"""Warm venv cache: skip the 30-90s venv+pip per build.

First build on a machine creates the template (venv + pytest) under
GENESIS_DATA_DIR/.venv-cache; every later build clones it in seconds.
Cache key: python major.minor. Clones are independent copies — builds can
never contaminate each other or the template. Any failure falls back to a
fresh venv, so this can only ever save time, never break a build.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _data_dir() -> Path:
    return Path(os.environ.get("GENESIS_DATA_DIR", "/tmp/genesis-data"))


def _cache_dir() -> Path:
    v = f"{sys.version_info.major}.{sys.version_info.minor}"
    return _data_dir() / ".venv-cache" / f"py{v}"


def _template_ok(d: Path) -> bool:
    vpy = d / "bin" / "python"
    if not vpy.is_file():
        return False
    try:
        p = subprocess.run([str(vpy), "-m", "pytest", "--version"],
                           capture_output=True, text=True, timeout=30)
        if p.returncode != 0:
            return False
        p = subprocess.run([str(vpy), "-m", "pip", "--version"],
                           capture_output=True, text=True, timeout=30)
        return p.returncode == 0
    except Exception:
        return False


def warm_venv(workdir: Path, timeout_s: int = 120) -> tuple[bool, str, str, str]:
    """Returns (ok, vpy, vpip, detail). Never raises."""
    venv = workdir / ".venv"
    cache = _cache_dir()
    try:
        if _template_ok(cache):
            if venv.exists():
                shutil.rmtree(venv)
            shutil.copytree(cache, venv, symlinks=True)
            if _template_ok(venv):
                return (True, str(venv / "bin" / "python"),
                        str(venv / "bin" / "pip"),
                        "venv ready from warm cache (skipped fresh install).")
    except Exception:
        pass
    # miss or broken clone: build fresh, then (best-effort) refresh the cache
    try:
        if venv.exists():
            shutil.rmtree(venv)
        proc = subprocess.run(["python3", "-m", "venv", str(venv)],
                              capture_output=True, text=True,
                              timeout=timeout_s, shell=False)
        if proc.returncode != 0:
            return (False, "", "",
                    f"venv failed: {proc.stderr[-500:]}")
        vpy, vpip = str(venv / "bin" / "python"), str(venv / "bin" / "pip")
        proc = subprocess.run([vpy, "-m", "pip", "install", "-q", "pytest"],
                              capture_output=True, text=True,
                              timeout=240, shell=False)
        if proc.returncode != 0:
            return (False, "", "",
                    f"pip failed: {(proc.stdout + proc.stderr)[-500:]}")
        try:
            tmp = cache.parent / f"tmp-{os.getpid()}"
            if tmp.exists():
                shutil.rmtree(tmp)
            shutil.copytree(venv, tmp, symlinks=True)
            if cache.exists():
                shutil.rmtree(cache)
            tmp.replace(cache)
        except Exception:
            pass
        return (True, vpy, vpip, "venv + pytest ready.")
    except subprocess.TimeoutExpired:
        return (False, "", "", "venv creation timed out.")
    except Exception as e:
        return (False, "", "", f"venv failed: {e}")
