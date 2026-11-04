"""Live build runs: background threads + step streaming for SSE.

One build = one Run. Steps append as agents finish them (with lane + ts),
so the studio can render Architect/Planner/Builder/Tester/Reviewer/Secure
working — including simultaneously — instead of one static report minutes
later.

Single-worker live streaming stays in memory. Website deployments
(GENESIS_REQUIRE_DB=1) also persist every snapshot to Postgres for history
and cross-worker reads; laptop mode keeps memory only. Never raises out of
the public helpers.
"""

from __future__ import annotations

import os
import threading
import time
import uuid

_runs: dict[str, dict] = {}
_lock = threading.Lock()


def _strict_db() -> bool:
    if os.environ.get("GENESIS_REQUIRE_DB") != "1":
        return False
    try:
        from ..db import pg as _pgmod
        return bool(_pgmod.db_url() and _pgmod.available())
    except Exception:
        return False


def _snapshot(run: dict) -> dict:
    return {
        "id": run["id"], "pid": run["pid"], "kind": run["kind"],
        "status": run["status"], "steps": [dict(s) for s in run["steps"]],
        "report": run["report"], "error": run["error"],
        "started_at": run["started_at"],
    }


def _persist(run: dict) -> None:
    if not _strict_db():
        return
    try:
        from ..db import pg as _pgmod
        con = _pgmod.connect()
        if con is None:
            return
        try:
            _pgmod.run_save(con, _snapshot(run))
        finally:
            try:
                con.close()
            except Exception:
                pass
    except Exception:
        pass


def _new_run(pid: str, kind: str) -> dict:
    return {
        "id": "run-" + uuid.uuid4().hex[:12],
        "pid": pid,
        "kind": kind,
        "status": "running",  # running | done | failed
        "steps": [],
        "report": None,
        "error": "",
        "started_at": int(time.time()),
        "done": threading.Event(),
    }


def start_run(pid: str, kind: str, fn, *args, **kwargs) -> str:
    """Run fn(*args, on_step=append, **kwargs) in a thread. Returns run_id."""
    run = _new_run(pid, kind)
    with _lock:
        _runs[run["id"]] = run

    def append(step: dict) -> None:
        with _lock:
            run["steps"].append(dict(step))
            snap = _snapshot(run)
        _persist(snap)

    def _execute() -> None:
        try:
            report = fn(*args, on_step=append, **kwargs)
            with _lock:
                run["report"] = report
                run["status"] = "done"
                snap = _snapshot(run)
        except Exception as e:  # noqa: BLE001 — a run must never hang SSE
            with _lock:
                run["error"] = f"{type(e).__name__}: {e}"
                run["status"] = "failed"
                snap = _snapshot(run)
        finally:
            run["done"].set()
        _persist(snap)

    threading.Thread(target=_execute, daemon=True,
                     name=f"genesis-{run['id']}").start()
    with _lock:
        _persist(_snapshot(run))
    return run["id"]


def get_run(run_id: str):
    with _lock:
        run = _runs.get(str(run_id))
        if run:
            return _snapshot(run)
    if not _strict_db():
        return None
    try:
        from ..db import pg as _pgmod
        con = _pgmod.connect()
        if con is None:
            return None
        try:
            doc = _pgmod.run_get(con, str(run_id))
        finally:
            try:
                con.close()
            except Exception:
                pass
    except Exception:
        return None
    if not isinstance(doc, dict) or not doc.get("id"):
        return None
    return {
        "id": doc.get("id"), "pid": doc.get("pid"), "kind": doc.get("kind"),
        "status": doc.get("status", "running"),
        "steps": list(doc.get("steps") or []),
        "report": doc.get("report"), "error": doc.get("error", ""),
        "started_at": doc.get("started_at", 0),
    }


def _live_run(run_id: str):
    with _lock:
        return _runs.get(str(run_id))


def wait_done(run_id: str, timeout: float = 20.0) -> bool:
    """Block until the run finishes (or timeout). Returns True if done."""
    run = _live_run(run_id)
    if not run:
        return True
    return run["done"].wait(timeout=timeout)
