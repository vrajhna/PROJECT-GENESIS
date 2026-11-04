"""Docker sandbox for untrusted generated applications (Part III).

The generated app is the untrusted artifact: it runs in a disposable
container — non-root, read-only rootfs, 512MB/1CPU, pid-capped, no host
credentials, published only on 127.0.0.1. Tests stay on the host (they are
ours) and hit the published port exactly as before.

Mode selection: GENESIS_SANDBOX=docker|venv|auto (default auto: docker when
the daemon answers and python:3.12-slim is present, else venv). The venv
fallback is honest and labeled in every report — it is NOT isolation.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

IMAGE = "python:3.12-slim"
_probe_cache: dict = {}


def docker_available() -> bool:
    if "ok" in _probe_cache:
        return bool(_probe_cache["ok"])
    ok = False
    try:
        v = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                           capture_output=True, text=True, timeout=10)
        if v.returncode == 0:
            img = subprocess.run(["docker", "image", "inspect", IMAGE],
                                 capture_output=True, timeout=10)
            ok = img.returncode == 0
    except (FileNotFoundError, OSError):
        ok = False
    _probe_cache["ok"] = ok
    return ok


def sandbox_mode() -> str:
    want = (os.environ.get("GENESIS_SANDBOX") or "auto").lower()
    if want == "docker":
        return "docker" if docker_available() else "venv"
    if want == "venv":
        return "venv"
    return "docker" if docker_available() else "venv"


def app_container_argv(workdir: Path, script: str, name: str, host_port: int) -> list[str]:
    """Pure: the exact container command. Container port is always 8000."""
    return ["docker", "run", "-d", "--rm", "--name", name,
            "-e", "GENESIS_BIND=0.0.0.0",
            "-p", f"127.0.0.1:{host_port}:8000",
            "-v", f"{workdir}:/app", "-w", "/app",
            "--user", "1000:1000",
            "--memory", "512m", "--cpus", "1", "--pids-limit", "128",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--read-only", "--tmpfs", "/tmp",
            IMAGE, "python", script, "--port", "8000"]


def launch_app(workdir: Path, vpy: str, script: str, port: int,
               log_path: Path) -> dict:
    """Start the generated app. Returns a handle: {"kind": "docker"|"proc", ...}.

    Raises on launch failure (caller records it as a start failure).
    """
    if sandbox_mode() == "docker":
        name = f"genesis-app-{uuid.uuid4().hex[:10]}"
        argv = app_container_argv(workdir, script, name, port)
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            raise RuntimeError(f"docker launch failed: {(proc.stdout + proc.stderr)[-300:]}")
        return {"kind": "docker", "name": name, "port": port}
    log_f = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen([vpy, script, "--port", str(port)],
                            cwd=str(workdir), stdout=log_f, stderr=subprocess.STDOUT)
    return {"kind": "proc", "proc": proc, "port": port}


def stop_app(handle: dict | None) -> None:
    if not handle:
        return
    if handle.get("kind") == "docker":
        try:
            subprocess.run(["docker", "rm", "-f", handle["name"]],
                           capture_output=True, timeout=20)
        except (FileNotFoundError, OSError):
            pass
        return
    proc = handle.get("proc")
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def app_logs(handle: dict | None, log_path: Path) -> str:
    if handle and handle.get("kind") == "docker":
        try:
            proc = subprocess.run(["docker", "logs", handle["name"]],
                                  capture_output=True, text=True, timeout=20)
            return (proc.stdout + proc.stderr)[-2000:]
        except (FileNotFoundError, OSError):
            return ""
    try:
        return log_path.read_text(encoding="utf-8")[-2000:]
    except OSError:
        return ""


def describe() -> str:
    if sandbox_mode() == "docker":
        return (f"docker:{IMAGE} (non-root 1000:1000, read-only rootfs, "
                "512MB/1CPU, localhost-only, disposable)")
    return "venv (host process — NOT isolated; set GENESIS_SANDBOX=docker)"
