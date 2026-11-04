"""Meta health states: no key / invalid key / unreachable / missing model / ok.

Network is fully faked — these tests never touch api.meta.ai.
A live check lives in test_meta_connection.py and needs a real key.
"""

import io
import urllib.error

import pytest

from app.intelligence import meta_health as mh


class FakeResp:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self, _n=-1):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _models(ids):
    import json
    return json.dumps({"object": "list",
                       "data": [{"id": i} for i in ids]}).encode()


def test_no_key_never_touches_network(monkeypatch):
    called = []
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network!")))
    out = mh.meta_health("", "muse-wonder-1.0", "muse-spark-1.3")
    assert out["status"] == "no_key"
    assert out["models"] == [] and out["missing"] == []


def test_invalid_key(monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b"{}"))

    monkeypatch.setattr("urllib.request.urlopen", boom)
    out = mh.meta_health("LLM_dead", "muse-wonder-1.0", "muse-spark-1.3")
    assert out["status"] == "invalid_key"
    assert "revoke" in out["detail"] or "valid" in out["detail"]


def test_unreachable(monkeypatch):
    def down(req, timeout=None):
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", down)
    out = mh.meta_health("LLM_x", "muse-wonder-1.0", "muse-spark-1.3")
    assert out["status"] == "unreachable"


def test_ok_with_both_models(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=None: FakeResp(_models(["muse-wonder-1.0", "muse-spark-1.3"])))
    out = mh.meta_health("LLM_live", "muse-wonder-1.0", "muse-spark-1.3")
    assert out["status"] == "ok"
    assert out["missing"] == []
    assert "muse-wonder-1.0" in out["models"]


def test_models_missing_flags_unknown_id(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=None: FakeResp(_models(["muse-spark-1.3"])))
    out = mh.meta_health("LLM_live", "muse-wonder-9.9", "muse-spark-1.3")
    assert out["status"] == "models_missing"
    assert out["missing"] == ["muse-wonder-9.9"]
    assert "META_ADVANCED_MODEL" in out["detail"]


def test_check_models_parses_catalog(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=None: FakeResp(_models(["a", "a", "b"])))
    out = mh.check_models("LLM_x")
    assert out["ok"] is True and out["models"] == ["a", "b"]


def test_health_endpoint_reports_meta_block(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.api import server as srv
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    srv.DATA_DIR = tmp_path / "data"
    srv.DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = TestClient(srv.app)
    h = c.get("/api/health").json()
    assert h["ok"] is True and h["meta"]["status"] == "no_key"
    r = c.post("/api/settings/meta/check")
    assert r.status_code == 200
    assert r.json()["meta"]["status"] == "no_key"


def test_require_db_gate(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.api import server as srv
    monkeypatch.setenv("GENESIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("GENESIS_REQUIRE_DB", "1")
    srv.DATA_DIR = tmp_path / "data"
    srv.DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = TestClient(srv.app)
    r = c.get("/api/health")
    assert r.status_code == 503
    assert "DATABASE_URL" in r.json()["error"]
