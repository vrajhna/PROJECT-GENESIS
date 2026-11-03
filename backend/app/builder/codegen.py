"""Model-driven code generation for the full-stack builder.

Genesis proper: the MODEL writes the app for ANY spec; the pipeline
(install -> start -> pytest -> review -> repair -> verify) proves it.
Templates in fullstack.py are the offline/no-key fallback, never the story.

Contract enforced here before a single byte is written:
  - exact file set, paths confined to the project workdir (no .., no /abs)
  - per-file + total size caps
  - no secret patterns, localhost bind present in backend/server.py
  - JSON-only model output, parsed defensively
Any violation -> caller falls back to templates. Never raises for
model-side problems; raises only for programmer errors (bad test fakes).
"""

from __future__ import annotations

import json
import re

ALLOWED_FILES = frozenset({
    "frontend/index.html",
    "frontend/app.js",
    "frontend/style.css",
    "backend/server.py",
    "tests/test_app.py",
    "requirements.txt",
    ".env.example",
    "SETUP.md",
})
REQUIRED_FILES = frozenset({
    "frontend/index.html",
    "frontend/app.js",
    "frontend/style.css",
    "backend/server.py",
    "tests/test_app.py",
})
MAX_FILE_BYTES = 200_000
MAX_TOTAL_BYTES = 400_000

SECRET_PATTERNS = (
    re.compile(r"sk-(live|test)-[A-Za-z0-9]{8,}"),
    re.compile(r"ghp_[A-Za-z0-9]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"BEGIN .*PRIVATE KEY"),
    re.compile(r"rzp_(live|test)_[A-Za-z0-9]+"),
)


def extract_text(data: dict) -> str:
    """Pull assistant text out of a /responses payload. Defensive: the API
    shape has changed before; never crash on an unknown envelope."""
    try:
        out = data.get("output") if isinstance(data, dict) else None
        if isinstance(out, list):
            chunks = []
            for item in out:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if isinstance(content, str):
                    chunks.append(content)
                elif isinstance(content, list):
                    for part in content:
                        if not isinstance(part, dict):
                            continue
                        if part.get("type") in ("output_text", "text"):
                            t = part.get("text")
                            if isinstance(t, dict) and isinstance(t.get("value"), str):
                                chunks.append(t["value"])
                            elif isinstance(t, str):
                                chunks.append(t)
            text = "".join(chunks).strip()
            if text:
                return text
        # fallbacks: some SDKs surface these
        for key in ("text", "content", "message"):
            v = data.get(key) if isinstance(data, dict) else None
            if isinstance(v, str) and v.strip():
                return v.strip()
    except Exception:
        pass
    return ""


def parse_files(text: str) -> dict:
    """Extract {"files": {...}} from model output. Raises ValueError."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in model output")
    try:
        doc = json.loads(cleaned[start:end + 1])
    except ValueError as e:
        raise ValueError(f"model output is not JSON: {e}")
    files = doc.get("files") if isinstance(doc, dict) else None
    if not isinstance(files, dict) or not files:
        raise ValueError("model output has no files map")
    return files


def validate_files(files: dict) -> tuple[bool, str]:
    """Returns (ok, reason). Pure function, fully unit-tested."""
    if not isinstance(files, dict) or not files:
        return False, "empty files map"
    total = 0
    for path, content in files.items():
        if path not in ALLOWED_FILES:
            return False, f"path not allowed: {path}"
        if not isinstance(content, str) or not content.strip():
            return False, f"empty file: {path}"
        size = len(content.encode("utf-8"))
        if size > MAX_FILE_BYTES:
            return False, f"file too big: {path}"
        total += size
        for pat in SECRET_PATTERNS:
            if pat.search(content):
                return False, f"secret pattern in {path}"
    if total > MAX_TOTAL_BYTES:
        return False, "output too big overall"
    missing = [f for f in REQUIRED_FILES if f not in files]
    if missing:
        return False, f"missing required files: {', '.join(missing)}"
    server = files.get("backend/server.py", "")
    if "127.0.0.1" not in server:
        return False, "backend must bind localhost only"
    return True, "ok"


def generate_with_model(spec: str, requirements: list, resources: list,
                        auth_on: bool, game_style: str,
                        client=None, router=None) -> dict:
    """Ask the model to write the app. Returns a result dict, never raises
    for model-side problems (callers fall back to templates on ok=False)."""
    try:
        from ..intelligence.meta_client import MetaClient, MetaConfig
        from ..intelligence.model_router import ModelRouter
        from ..intelligence.prompt_manager import render
    except ImportError as e:
        return {"ok": False, "error": f"prompt stack unavailable: {e}",
                "fallback": True}
    try:
        if client is None:
            if router is not None and getattr(router, "client", None) is not None:
                client = router.client
            else:
                cfg = MetaConfig.from_env()
                # Full-app generation is long output; give the model room even
                # when the env default is tuned for quick chat calls.
                if cfg.timeout_s < 120:
                    cfg.timeout_s = 120
                client = MetaClient(cfg)
        if not client.config.api_key:
            return {"ok": False, "error": "MODEL_API_KEY is not set",
                    "fallback": True}
        router = router or ModelRouter(client)
        # "multi-file" routes to the ADVANCED model by design (see
        # ModelRouter.COMPLEX_HINTS): code generation always gets Wonder,
        # never the fast model. Set META_ADVANCED_MODEL to use a specific
        # Wonder variant (e.g. a Wonder Full ID) without touching code.
        req_lines = "\n".join(
            f"- {r.get('id', '?')}: {r.get('description', '')}"
            for r in (requirements or []))
        _, prompt = render("codegen.fullstack", {
            "spec": spec,
            "requirements": req_lines,
            "resources": ", ".join(resources) if resources else "(none)",
            "auth": "on" if auth_on else "off",
            "game": game_style or "none",
        })
        routed = router.run("multi-file codegen", prompt)
        if not routed.get("ok"):
            return {"ok": False,
                    "error": str(routed.get("error") or "model call failed"),
                    "fallback": True}
        text = extract_text(routed.get("data") or {})
        if not text:
            return {"ok": False, "error": "empty model reply",
                    "fallback": True}
        files = parse_files(text)
        ok, reason = validate_files(files)
        if not ok:
            return {"ok": False, "error": f"contract rejected: {reason}",
                    "fallback": True}
        model = str(routed.get("model") or "model")
        latency = int(routed.get("latency_ms") or 0)
        return {"ok": True, "files": files, "model": model,
                "latency_ms": latency}
    except (ValueError, KeyError) as e:
        return {"ok": False, "error": f"bad model output: {e}",
                "fallback": True}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "fallback": True}
