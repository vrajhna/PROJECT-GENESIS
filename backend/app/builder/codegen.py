"""Model-driven code generation for the full-stack builder.

Genesis proper: the MODEL writes the app for ANY spec; the pipeline
(install -> start -> pytest -> review -> repair -> verify) proves it.
Templates in fullstack.py are the offline/no-key fallback, never the story.

Contract enforced here before a single byte is written:
  - exact file set, paths confined to the project workdir (no .., no /abs)
  - per-file + total size caps
  - no secret patterns, GENESIS_BIND honored with a localhost default in
    backend/server.py (a hardcoded loopback bind is deterministically
    adapted; any world bind is rejected)
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


def ensure_sandbox_bind(files: dict) -> tuple[dict, bool]:
    """Deterministic bind adapter for model-written servers.

    A hardcoded 127.0.0.1 bind is unreachable inside the Docker sandbox
    (proven live with Wonder output): the container must listen on all
    interfaces while Docker publishes only to host loopback. When the
    model ignored the GENESIS_BIND contract, rewrite the bind tuple to
    honor GENESIS_BIND with a 127.0.0.1 default — loopback behavior is
    unchanged everywhere the variable is unset. Returns (files, adapted).
    Anything already world-bound is left untouched for the validator to
    reject; this adapter never widens a bind, it only parameterizes a
    loopback one.
    """
    server = files.get("backend/server.py")
    if not isinstance(server, str) or "GENESIS_BIND" in server:
        return files, False
    if '"0.0.0.0"' in server or "'0.0.0.0'" in server:
        return files, False
    needle = None
    for quote in ('"', "'"):
        for pre in ("", " "):
            for post in ("", " "):
                cand = "(" + pre + quote + "127.0.0.1" + quote + post + ","
                if cand in server:
                    needle = (cand, "(" + pre + "os.environ.get(" + quote
                              + "GENESIS_BIND" + quote + ", " + quote
                              + "127.0.0.1" + quote + ")" + post + ",")
                    break
            if needle is not None:
                break
        if needle is not None:
            break
    if needle is None:
        return files, False
    if not any(line.startswith("import os") for line in server.splitlines()):
        server = "import os\n" + server
    out = dict(files)
    out["backend/server.py"] = server.replace(needle[0], needle[1], 1)
    return out, True


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
    if ('"0.0.0.0"' in server or "'0.0.0.0'" in server
            or 'GENESIS_BIND", "0.0.0.0"' in server):
        return False, "backend must bind localhost only (world bind forbidden)"
    if "GENESIS_BIND" not in server or "127.0.0.1" not in server:
        return False, ("backend must honor GENESIS_BIND with a localhost "
                       "(127.0.0.1) default")
    return True, "ok"


def _is_model_missing(error: str) -> bool:
    """404/model_not_found (bad ID for this key) deserves a retry with the
    other model; every other failure goes straight to templates."""
    e = (error or "").lower()
    return "model_not_found" in e or "model not found" in e or "http 404" in e


def generate_with_model(spec: str, requirements: list,
                        client=None, router=None, on_progress=None) -> dict:
    """Ask the model to write the app. The model designs everything from
    the spec + requirements — no keyword steering reaches it. Returns a
    result dict, never raises for model-side problems (callers fall back
    to templates on ok=False). When on_progress is given (and no test
    router is injected), generation streams and on_progress(chars,
    elapsed_s) fires as tokens arrive — throttled by the caller."""
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
                if cfg.timeout_s < 300:
                    cfg.timeout_s = 300
                client = MetaClient(cfg)
        if not client.config.api_key:
            return {"ok": False, "error": "MODEL_API_KEY is not set",
                    "fallback": True}
        use_stream = (on_progress is not None and router is None
                      and hasattr(client, "respond_stream"))
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
        })
        tried: list = []
        if use_stream:
            model = router.pick_model("multi-file codegen")
            routed = client.respond_stream(model, prompt,
                                           task="multi-file codegen",
                                           on_progress=on_progress)
            routed["model"] = model
            routed["task_kind"] = "multi-file codegen"
        else:
            routed = router.run("multi-file codegen", prompt)
        tried.append(str(routed.get("model") or "?"))
        if not routed.get("ok") and _is_model_missing(str(routed.get("error") or "")):
            if use_stream:
                model = router.pick_model("routine codegen")
                fallback_res = client.respond_stream(
                    model, prompt, task="routine codegen",
                    on_progress=on_progress)
                fallback_res["model"] = model
                fallback_res["task_kind"] = "routine codegen"
            else:
                fallback_res = router.run("routine codegen", prompt)
            tried.append(str(fallback_res.get("model") or "?"))
            routed = fallback_res
        if not routed.get("ok"):
            return {"ok": False,
                    "error": f"models tried [{', '.join(tried)}]: "
                             f"{routed.get('error') or 'model call failed'}",
                    "fallback": True,
                    "tried": tried}
        text = extract_text(routed.get("data") or {})
        if not text:
            return {"ok": False, "error": "empty model reply",
                    "fallback": True}
        files = parse_files(text)
        files, normalized = ensure_sandbox_bind(files)
        ok, reason = validate_files(files)
        if not ok:
            return {"ok": False, "error": f"contract rejected: {reason}",
                    "fallback": True}
        model = str(routed.get("model") or "model")
        latency = int(routed.get("latency_ms") or 0)
        result = {"ok": True, "files": files, "model": model,
                  "latency_ms": latency}
        if normalized:
            result["normalized_bind"] = True
        return result
    except (ValueError, KeyError) as e:
        return {"ok": False, "error": f"bad model output: {e}",
                "fallback": True}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "fallback": True}
