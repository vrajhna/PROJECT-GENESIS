"""Genesis terminal pack: intelligence status, downloads, CLI behavior."""

import io
import subprocess
import sys
import zipfile
from pathlib import Path

CLI = Path(__file__).resolve().parent.parent / "genesis-cli" / "genesis"


def _client(tmp_path):
    from fastapi.testclient import TestClient
    from app.api import server as srv
    srv.DATA_DIR = tmp_path / "data"
    return TestClient(srv.app)


def test_status_reports_backing_without_leaking_secrets(tmp_path):
    body = _client(tmp_path).get("/api/intelligence/status").json()
    assert body["ok"] is True
    assert body["models"]["primary"] and body["models"]["advanced"]
    assert isinstance(body["models"]["key_configured"], bool)
    assert "ArchitectAgent" in body["agents"]
    assert body["tools"]["count"] >= 14
    assert isinstance(body["skills"]["count"], int)
    raw = str(body)
    assert "MODEL_API_KEY" not in raw


def test_cli_pack_downloads_and_runs(tmp_path):
    blob = _client(tmp_path).get("/api/download/cli").content
    names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
    assert "genesis-cli/genesis" in names
    assert "genesis-cli/install.sh" in names
    assert "genesis-cli/install.ps1" in names


def test_engine_pack_contains_server_and_cli(tmp_path):
    blob = _client(tmp_path).get("/api/download/engine").content
    names = zipfile.ZipFile(io.BytesIO(blob)).namelist()
    assert "genesis-engine/app/api/server.py" in names
    assert "genesis-engine/genesis-cli/genesis" in names


def test_cli_auto_upload_policy_offline(tmp_path):
    import os
    env = dict(os.environ, GENESIS_URL="http://127.0.0.1:9")
    r = subprocess.run([sys.executable, str(CLI), "auto", "hello"],
                       capture_output=True, text=True, timeout=30, env=env)
    assert r.returncode == 1 and "cannot reach" in r.stdout
    r = subprocess.run([sys.executable, str(CLI), "upload", "/nonexistent.zip"],
                       capture_output=True, text=True, timeout=30, env=env)
    assert r.returncode == 1 and "no such file" in r.stdout
    r = subprocess.run([sys.executable, str(CLI), "policy", "x", "on"],
                       capture_output=True, text=True, timeout=30, env=env)
    assert r.returncode == 1 and "cannot reach" in r.stdout


def test_multipart_encoder_names_the_file(tmp_path):
    import importlib.util
    from importlib.machinery import SourceFileLoader
    z = tmp_path / "code.zip"
    zipfile.ZipFile(z, "w").writestr("a.txt", "hi")
    loader = SourceFileLoader("genesiscli", str(CLI))
    spec = importlib.util.spec_from_file_location("genesiscli", str(CLI), loader=loader)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    body, boundary = mod._multipart(str(z))
    assert boundary.encode() in body and b'filename="code.zip"' in body


def test_cli_help_and_offline_error_are_clean(tmp_path):
    r = subprocess.run([sys.executable, str(CLI), "build", "--help"],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0 and "--db" in r.stdout
    import os
    env = dict(os.environ, GENESIS_URL="http://127.0.0.1:9")
    r = subprocess.run([sys.executable, str(CLI), "status"],
                       capture_output=True, text=True, timeout=30, env=env)
    assert r.returncode == 1 and "cannot reach" in r.stdout


def test_installers_download(tmp_path):
    c = _client(tmp_path)
    sh = c.get("/api/download/install.sh")
    assert sh.status_code == 200 and "genesis cli" in sh.text.lower()
    ps1 = c.get("/api/download/install.ps1")
    assert ps1.status_code == 200 and ".genesis" in ps1.text


def test_empty_zip_means_missing(tmp_path):
    from app.api import server as srv
    assert srv._zip_tree(tmp_path, ["nope-missing"], "") == b""


def test_cli_login_offline_and_talk_quit(tmp_path):
    import os
    env = dict(os.environ, GENESIS_URL="http://127.0.0.1:9")
    r = subprocess.run([sys.executable, str(CLI), "login", "a@b.co"],
                       capture_output=True, text=True, timeout=30, env=env)
    assert r.returncode == 1 and "cannot reach" in r.stdout
    r = subprocess.run([sys.executable, str(CLI), "talk", "proj-x"],
                       input="/quit\n", capture_output=True, text=True,
                       timeout=30, env=env)
    assert r.returncode == 0 and "talking to genesis" in r.stdout


def test_cli_token_header_and_save(tmp_path, monkeypatch):
    import importlib.util
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("genesiscli", str(CLI))
    spec = importlib.util.spec_from_file_location("genesiscli", str(CLI), loader=loader)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "TOKEN_FILE", str(tmp_path / "token"))
    monkeypatch.delenv("GENESIS_TOKEN", raising=False)
    assert mod._auth_headers() == {}
    mod._save_token("tok-123")
    assert mod._auth_headers() == {"Authorization": "Bearer tok-123"}
    monkeypatch.setenv("GENESIS_TOKEN", "tok-env")
    assert mod._auth_headers() == {"Authorization": "Bearer tok-env"}
