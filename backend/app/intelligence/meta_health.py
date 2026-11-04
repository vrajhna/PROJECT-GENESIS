"""Meta API health: key validity + model availability, no secrets ever.

States (machine-readable `status`, human `detail`):
  no_key          MODEL_API_KEY unset — everything model-backed is off.
  invalid_key     API answered 401 — key revoked/wrong (rotate in dashboard).
  unreachable     Network/DNS/timeout — API cannot be reached at all.
  models_missing  Key works but a configured model ID is not in the
                  catalog (wrong ID or no entitlement on this key).
  ok              Key works and both configured models are listed.

Only status strings and model IDs leave this module. Keys are never
stored, logged, or returned. All network I/O is bounded (8s) and
exception-proof: this module must never break boot or health checks.
"""

from __future__ import annotations

import time

_TIMEOUT_S = 8.0


def check_models(api_key: str, base_url: str = "https://api.meta.ai/v1",
                 timeout: float = _TIMEOUT_S) -> dict:
    """GET {base}/models. Returns {ok, models|error, kind, latency_ms}.
    `kind` is one of: ok | invalid_key | unreachable. Never raises."""
    import urllib.request
    import urllib.error

    if not (api_key or "").strip():
        return {"ok": False, "kind": "no_key",
                "error": "MODEL_API_KEY is not set", "latency_ms": 0}
    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + api_key}, method="GET")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            import json
            data = json.loads(resp.read(200000).decode("utf-8", "replace") or "{}")
            latency_ms = int((time.monotonic() - start) * 1000)
    except urllib.error.HTTPError as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        if e.code == 401:
            return {"ok": False, "kind": "invalid_key",
                    "error": "HTTP 401 invalid_api_key: key revoked or never valid — "
                             "create a fresh one in the Model API dashboard",
                    "latency_ms": latency_ms}
        return {"ok": False, "kind": "unreachable",
                "error": f"HTTP {e.code} from models endpoint",
                "latency_ms": latency_ms}
    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {"ok": False, "kind": "unreachable",
                "error": f"{type(e).__name__}: {e}", "latency_ms": latency_ms}
    ids: list[str] = []
    try:
        items = data.get("data") if isinstance(data, dict) else None
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict) and isinstance(it.get("id"), str):
                    ids.append(it["id"])
    except Exception:
        ids = []
    return {"ok": True, "kind": "ok", "models": sorted(set(ids)),
            "latency_ms": latency_ms}


def meta_health(api_key: str = "", advanced_model: str = "",
                primary_model: str = "",
                base_url: str = "https://api.meta.ai/v1") -> dict:
    """Full startup verdict. Never raises, never touches the network
    without a key, never returns key material."""
    if not (api_key or "").strip():
        return {"status": "no_key",
                "detail": "MODEL_API_KEY is not set — model features off, "
                          "templates carry every build",
                "models": [], "missing": [], "latency_ms": 0}
    res = check_models(api_key, base_url)
    if not res["ok"]:
        if res["kind"] == "invalid_key":
            return {"status": "invalid_key", "detail": res["error"],
                    "models": [], "missing": [], "latency_ms": res["latency_ms"]}
        return {"status": "unreachable", "detail": res["error"],
                "models": [], "missing": [], "latency_ms": res["latency_ms"]}
    catalog = res["models"]
    missing = [m for m in [advanced_model, primary_model] if m and m not in catalog]
    if missing:
        return {"status": "models_missing",
                "detail": "key works, but these configured IDs are not in "
                          f"its catalog: {', '.join(missing)} — fix "
                          "META_ADVANCED_MODEL / META_PRIMARY_MODEL",
                "models": catalog, "missing": missing,
                "latency_ms": res["latency_ms"]}
    return {"status": "ok",
            "detail": f"key valid; {advanced_model or '?'} + "
                      f"{primary_model or '?'} available "
                      f"({res['latency_ms']}ms)",
            "models": catalog, "missing": [],
            "latency_ms": res["latency_ms"]}
