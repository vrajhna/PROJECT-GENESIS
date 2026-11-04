"""Model-assisted repair: diagnosis + execution evidence in, a validated
minimal patch out.

The agent never writes files itself. `propose()` returns a patch that has
already passed `validate_patch` (workdir-confined, exact single match, no
secret patterns, size-capped); the caller applies it after snapshotting the
original bytes and rolls back when tests still fail. With no usable model
(no key / unreachable / contract rejected) it returns ok=False with the
reason — the caller then stops honestly. Never raises for model-side
problems; raises only for programmer errors (bad test fakes).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..builder.codegen import SECRET_PATTERNS

MAX_REPAIR_ATTEMPTS = 2
MAX_REPLACE_BYTES = 64_000
MAX_EVIDENCE_FILES = 6
MAX_FILE_EVIDENCE_BYTES = 8_000


def parse_patch(text: str) -> dict:
    """Extract {"patches": [...], "summary": ...} from model output.

    Raises ValueError on anything unparseable (caller treats as failure).
    """
    cleaned = (text or "").strip()
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
        raise ValueError(f"model output is not JSON: {e}") from e
    patches = doc.get("patches") if isinstance(doc, dict) else None
    if not isinstance(patches, list):
        raise ValueError("model output has no patches list")
    return {"patches": patches, "summary": str(doc.get("summary") or "")[:300]}


def validate_patch(workdir: Path, patch: dict) -> tuple[bool, str]:
    """Pure gate: is this patch safe to apply inside workdir right now?"""
    if not isinstance(patch, dict):
        return False, "patch is not an object"
    rel = patch.get("path")
    find = patch.get("find")
    replace = patch.get("replace")
    if not isinstance(rel, str) or not rel or rel.startswith(("/", "\\")):
        return False, "bad patch path"
    if any(part in ("..",) for part in Path(rel).parts):
        return False, f"path escapes workdir: {rel}"
    root = workdir.resolve()
    target = (root / rel).resolve()
    if root not in target.parents and target != root:
        return False, f"path escapes workdir: {rel}"
    if any(part in (".venv", ".git", "__pycache__", ".genesis") for part in target.parts):
        return False, f"refusing to patch generated/cache file: {rel}"
    if not target.is_file():
        return False, f"no such file: {rel}"
    if not isinstance(find, str) or not find:
        return False, "find block must be a non-empty string"
    if not isinstance(replace, str):
        return False, "replace must be a string"
    if len(replace.encode("utf-8")) > MAX_REPLACE_BYTES:
        return False, "replacement too large"
    for pat in SECRET_PATTERNS:
        if pat.search(replace):
            return False, "secret pattern in replacement"
    try:
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False, f"unreadable file: {rel}"
    count = content.count(find)
    if count == 0:
        return False, f"find block matches zero times in {rel}"
    if count > 1:
        return False, f"find block matches {count} times in {rel}; narrow the context"
    return True, "ok"


class RepairAgent:
    """Proposes minimal patches from execution evidence (ModelRouter-backed).

    task kind "debug repair proposal" contains "debug", so the router sends
    it to the ADVANCED model by design — repairs deserve the strong model.
    """

    name = "repair"

    def __init__(self, router=None, client=None) -> None:
        self.router = router
        self.client = client
        self.audit_log: list[str] = []

    def propose(self, workdir: Path, diagnosis: dict, failure_output: str,
                files: list[str]) -> dict:
        try:
            from ..intelligence.meta_client import MetaClient, MetaConfig
            from ..intelligence.model_router import ModelRouter
            from ..intelligence.prompt_manager import render
        except ImportError as e:
            return {"ok": False, "error": f"prompt stack unavailable: {e}"}
        try:
            client = self.client
            router = self.router
            if client is None and router is not None and getattr(router, "client", None) is not None:
                client = router.client
            if client is None:
                cfg = MetaConfig.from_env()
                if cfg.timeout_s < 120:
                    cfg.timeout_s = 120
                client = MetaClient(cfg)
            if not client.config.api_key:
                return {"ok": False, "error": "MODEL_API_KEY is not set"}
            router = router or ModelRouter(client)

            evidence = [f"DIAGNOSIS:\n{json.dumps(diagnosis, indent=2)[:4000]}",
                        f"FAILURE OUTPUT (tail):\n{failure_output[-6000:]}"]
            # Evidence is gathered through the tool registry (confined reads,
            # audit-logged). Direct reads remain only as a fallback.
            registry = None
            try:
                from ..builder.approvals import ApprovalGate
                from ..builder.files import GenesisWorkspace
                from ..tools.registry import ToolRegistry
                registry = ToolRegistry(GenesisWorkspace(workdir), ApprovalGate())
            except Exception:
                registry = None
            shown = 0
            for rel in files:
                if shown >= MAX_EVIDENCE_FILES:
                    break
                target = (workdir / rel)
                if not target.is_file():
                    continue
                text = None
                if registry is not None:
                    res = registry.call("read_file", {"path": rel})
                    if res.get("ok"):
                        text = res.get("content") or ""
                if text is None:
                    try:
                        text = target.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError):
                        continue
                evidence.append(f"FILE {rel}:\n{text[:MAX_FILE_EVIDENCE_BYTES]}")
                shown += 1
            self.audit_log = [c.tool for c in registry.audit] if registry else []
            _, prompt = render("repair.propose", {"failure": "\n\n".join(evidence)})
            routed = router.run("debug repair proposal", prompt)
            if not routed.get("ok"):
                return {"ok": False,
                        "error": f"model call failed: {routed.get('error') or 'unknown'}"}
            from ..builder.codegen import extract_text
            parsed = parse_patch(extract_text(routed.get("data") or {}))
            patches = parsed["patches"]
            if not patches:
                return {"ok": False, "error": "model proposed no patch",
                        "summary": parsed["summary"]}
            for patch in patches:
                ok, reason = validate_patch(workdir, patch)
                if not ok:
                    return {"ok": False, "error": f"patch rejected: {reason}",
                            "summary": parsed["summary"]}
            return {"ok": True, "patches": patches, "summary": parsed["summary"],
                    "model": str(routed.get("model") or "model"),
                    "latency_ms": int(routed.get("latency_ms") or 0)}
        except (ValueError, KeyError) as e:
            return {"ok": False, "error": f"bad model output: {e}"}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
