"""Targeted patch editing: exact single-match replacement only.

No full-file rewrites. Zero matches or multiple matches raise — the caller
must narrow the context. This is the only mutation primitive the repair
engine (Phase-5) may use.
"""

from __future__ import annotations

from pathlib import Path


def apply_patch(path: Path, find: str, replace: str) -> dict:
    if not find:
        raise ValueError("find block must not be empty")
    text = path.read_text(encoding="utf-8")
    count = text.count(find)
    if count == 0:
        raise LookupError("find block matches zero times")
    if count > 1:
        raise LookupError(f"find block matches {count} times; narrow the context")
    path.write_text(text.replace(find, replace, 1), encoding="utf-8")
    return {
        "ok": True,
        "path": str(path),
        "old_chars": len(text),
        "new_chars": len(text) - len(find) + len(replace),
    }
