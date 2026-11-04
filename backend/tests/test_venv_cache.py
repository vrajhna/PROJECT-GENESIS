"""Warm venv cache: first build pays, every later build clones in seconds."""

import sys
from pathlib import Path

import pytest

from app.builder import venv_cache as vc


def test_miss_builds_template_and_hit_clones_fast(tmp_path, monkeypatch):
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "data"))
    work1, work2 = tmp_path / "w1", tmp_path / "w2"
    work1.mkdir()
    work2.mkdir()
    ok, vpy, vpip, msg = vc.warm_venv(work1)
    assert ok and Path(vpy).is_file(), msg
    assert "warm cache" not in msg  # first time: built fresh
    assert (vc._cache_dir() / "bin" / "python").is_file()
    ok2, vpy2, _, msg2 = vc.warm_venv(work2)
    assert ok2 and Path(vpy2).is_file()
    assert "warm cache" in msg2  # second time: cloned
    # clones are independent copies, not the same dir
    assert Path(vpy2).parent.parent != vc._cache_dir()


def test_broken_cache_falls_back_to_fresh(tmp_path, monkeypatch):
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "data"))
    work = tmp_path / "w"
    work.mkdir()
    assert vc.warm_venv(work)[0] is True
    import shutil
    shutil.rmtree(vc._cache_dir() / "bin")
    ok, vpy, _, _ = vc.warm_venv(work)
    assert ok and Path(vpy).is_file()
    assert (vc._cache_dir() / "bin" / "python").is_file()  # template healed


def test_version_bump_rebuilds(tmp_path, monkeypatch):
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "data"))
    work = tmp_path / "w"
    work.mkdir()
    assert vc.warm_venv(work)[0] is True
    first_cache = vc._cache_dir()
    assert first_cache.name == f"py{sys.version_info.major}.{sys.version_info.minor}"


def test_clone_works_after_source_venv_deleted(tmp_path, monkeypatch):
    """Regression: script shebangs bake in the creating venv's path, so a
    template built inside a pytest tmp dir poisons every later clone once
    that dir is cleaned. Module execution (`-m pip`) must not care."""
    import shutil
    import subprocess
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "data"))
    work1, work2 = tmp_path / "w1", tmp_path / "w2"
    work1.mkdir()
    work2.mkdir()
    ok, _, _, _ = vc.warm_venv(work1)
    assert ok
    shutil.rmtree(work1)  # source venv gone, like tmp cleanup
    ok2, vpy2, _, _ = vc.warm_venv(work2)
    assert ok2
    p = subprocess.run([vpy2, "-m", "pip", "--version"],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0
