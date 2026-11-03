"""Guarded local execution placeholder for the vertical slice.

NOT the production sandbox: production requires Docker non-root, CPU/mem
limits, restricted mounts/net, no host credentials. This helper runs an
explicit argv with a timeout, captures output, and never uses a shell.
"""

from __future__ import annotations

import subprocess


def run_guarded(argv: list[str], timeout_s: int = 15, cwd: str | None = None) -> dict:
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=cwd,
            shell=False,
        )
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit_code": -1, "stdout": "", "stderr": "timeout"}
    except Exception as e:
        return {"ok": False, "exit_code": -1, "stdout": "", "stderr": f"{type(e).__name__}: {e}"}
