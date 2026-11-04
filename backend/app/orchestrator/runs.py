"""Live build runs: background threads + step streaming for SSE.

One build = one Run. Steps append as agents finish them (with lane + ts),
so the studio can render Architect/Planner/Builder/Tester/Reviewer/Secure
working — including simultaneously — instead of one static report minutes
later.

Single-worker safe (in-memory registry). A shared cross-worker store
arrives with the build queue (M4). Never raises out of the public helpers.
"""

from __future__ import annotations

import threading
import time
import uuid

_runs: dict[str, dict] = {}
_lock = threading.Lock()


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

    def _execute() -> None:
        try:
            report = fn(*args, on_step=append, **kwargs)
            with _lock:
                run["report"] = report
                run["status"] = "done"
        except Exception as e:  # noqa: BLE001 — a run must never hang SSE
            with _lock:
                run["error"] = f"{type(e).__name__}: {e}"
                run["status"] = "failed"
        finally:
            run["done"].set()

    threading.Thread(target=_execute, daemon=True,
                     name=f"genesis-{run['id']}").start()
    return run["id"]


def get_run(run_id: str):
    with _lock:
        run = _runs.get(str(run_id))
        if not run:
            return None
        return {
            "id": run["id"],
            "pid": run["pid"],
            "kind": run["kind"],
            "status": run["status"],
            "steps": [dict(s) for s in run["steps"]],
            "report": run["report"],
            "error": run["error"],
            "started_at": run["started_at"],
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
