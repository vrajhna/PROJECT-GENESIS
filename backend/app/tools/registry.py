"""Centralized tool registry (Part VI).

Every tool declares: typed input/output schema, permission requirement,
timeout, and audit logging. The model may PROPOSE a call; the backend
validates schema + permission BEFORE execution. No tool gives models
direct host-shell access — run_command takes an argv list, never a string.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..agents.roles import ReviewerAgent, TestingAgent
from ..builder.approvals import ApprovalGate
from ..builder.checkpoints import create_checkpoint, restore_checkpoint
from ..builder.files import GenesisWorkspace
from ..builder.patches import apply_patch

OPEN = "open"          # safe to run any time
APPROVAL = "approval"  # needs an approved ApprovalGate item first


@dataclass
class ToolCall:
    time: str
    tool: str
    args: dict
    ok: bool
    detail: str = ""


@dataclass
class Tool:
    name: str
    description: str
    required: list[str]
    permission: str
    timeout_s: int


TOOLS: list[Tool] = [
    Tool("inspect_project", "List files under the workspace (capped).", [], OPEN, 10),
    Tool("read_file", "Read a workspace file.", ["path"], OPEN, 10),
    Tool("search_code", "Literal search across code and docs (capped).", ["query"], OPEN, 20),
    Tool("create_file", "Create/overwrite a workspace file (guarded).", ["path", "content"], OPEN, 10),
    Tool("apply_patch", "Single-match patch edit.", ["path", "find", "replace"], OPEN, 10),
    Tool("run_command", "Run an argv list, no shell. Approval required.", ["argv"], APPROVAL, 60),
    Tool("run_tests", "Execute pytest and parse results.", [], OPEN, 180),
    Tool("get_test_results", "Last stored test result.", [], OPEN, 5),
    Tool("get_runtime_logs", "Last stored runtime output.", [], OPEN, 5),
    Tool("inspect_dependencies", "Show declared dependency manifests.", [], OPEN, 10),
    Tool("create_git_checkpoint", "Commit workspace state, return SHA.", ["message"], OPEN, 30),
    Tool("restore_checkpoint", "Reset workspace to a SHA. Approval required.", ["sha"], APPROVAL, 30),
    Tool("generate_documentation", "Write a runbook from audit + results.", [], OPEN, 10),
    Tool("request_approval", "Open an approval item for a consequential action.", ["action"], OPEN, 5),
]


class ToolRegistry:
    def __init__(self, workspace: GenesisWorkspace, gate: ApprovalGate) -> None:
        self.workspace = workspace
        self.gate = gate
        self.audit: list[ToolCall] = []
        self._store: dict[str, str] = {}
        self.tools = {t.name: t for t in TOOLS}

    def _log(self, tool: str, args: dict, ok: bool, detail: str = "") -> None:
        self.audit.append(ToolCall(
            time=datetime.now(timezone.utc).isoformat(),
            tool=tool, args={k: (str(v)[:200]) for k, v in args.items()},
            ok=ok, detail=detail[:500]))

    def call(self, name: str, args: dict | None = None, approved: bool = False) -> dict:
        args = args or {}
        tool = self.tools.get(name)
        if tool is None:
            self._log(name, args, False, "unknown tool")
            return {"ok": False, "error": f"unknown tool: {name}"}
        missing = [k for k in tool.required if k not in args]
        if missing:
            self._log(name, args, False, f"missing: {missing}")
            return {"ok": False, "error": f"missing required args: {missing}"}
        if tool.permission == APPROVAL and not approved:
            self._log(name, args, False, "approval required")
            return {"ok": False, "error": f"{name} requires an approved approval item"}
        try:
            result = self._dispatch(name, args, tool.timeout_s)
            self._log(name, args, bool(result.get("ok", True)), result.get("summary", ""))
            return result
        except Exception as e:
            self._log(name, args, False, f"{type(e).__name__}: {e}")
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def _dispatch(self, name: str, args: dict, timeout_s: int) -> dict:
        root = self.workspace.root
        if name == "inspect_project":
            files = sorted(str(p.relative_to(root)) for p in root.rglob("*")
                           if p.is_file() and ".git" not in p.parts
                           and "__pycache__" not in p.parts)[:200]
            return {"ok": True, "files": files, "summary": f"{len(files)} file(s)"}
        if name == "read_file":
            return {"ok": True, "content": self.workspace.read_file(args["path"])}
        if name == "search_code":
            q = args["query"]
            hits = []
            for p in root.rglob("*"):
                if not p.is_file() or p.suffix not in (".py", ".ts", ".tsx", ".md", ".json", ".txt", ".toml", ".yaml", ".yml"):
                    continue
                if ".git" in p.parts or "__pycache__" in p.parts or len(hits) >= 50:
                    continue
                try:
                    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                        if q in line:
                            hits.append(f"{p.relative_to(root)}:{i}:{line.strip()[:120]}")
                            if len(hits) >= 50:
                                break
                except (OSError, UnicodeDecodeError):
                    continue
            return {"ok": True, "hits": hits, "summary": f"{len(hits)} hit(s)"}
        if name == "create_file":
            self.workspace.create_file(args["path"], args["content"],
                                       overwrite=bool(args.get("overwrite", False)))
            return {"ok": True, "summary": f"wrote {args['path']}"}
        if name == "apply_patch":
            target = self.workspace._resolve(args["path"])
            res = apply_patch(target, args["find"], args["replace"])
            return {"ok": True, "summary": f"patched {args['path']}", **res}
        if name == "run_command":
            argv = args["argv"]
            if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
                return {"ok": False, "error": "argv must be a list of strings (no shell)"}
            proc = subprocess.run(argv, cwd=str(root), capture_output=True, text=True,
                                  timeout=timeout_s, shell=False)
            out = (proc.stdout + proc.stderr)[-4000:]
            self._store["runtime_logs"] = out
            return {"ok": proc.returncode == 0, "exit_code": proc.returncode,
                    "output": out, "summary": f"exit {proc.returncode}"}
        if name == "run_tests":
            res = TestingAgent().run(root, timeout_s=timeout_s)
            self._store["test_results"] = res.summary + " " + (res.data.get("interpretation", ""))
            return {"ok": res.ok, "summary": res.summary, "data": res.data,
                    "evidence": res.evidence}
        if name == "get_test_results":
            return {"ok": True, "result": self._store.get("test_results", "no tests run yet")}
        if name == "get_runtime_logs":
            return {"ok": True, "logs": self._store.get("runtime_logs", "no commands run yet")}
        if name == "inspect_dependencies":
            manifests = {}
            for fname in ("requirements.txt", "package.json", "pyproject.toml"):
                p = root / fname
                if p.exists():
                    manifests[fname] = p.read_text(encoding="utf-8")[:2000]
            return {"ok": True, "manifests": manifests,
                    "summary": f"{len(manifests)} manifest(s)"}
        if name == "create_git_checkpoint":
            sha = create_checkpoint(root, args["message"])
            return {"ok": True, "sha": sha, "summary": f"checkpoint {sha[:8]}"}
        if name == "restore_checkpoint":
            restore_checkpoint(root, args["sha"])
            return {"ok": True, "summary": f"restored {args['sha'][:8]}"}
        if name == "generate_documentation":
            lines = ["# Runbook (generated)", ""]
            for entry in self.audit:
                lines.append(f"- {entry.time} {entry.tool} ok={entry.ok} {entry.detail}")
            lines += ["", "## Last test results", self._store.get("test_results", "none")]
            self.workspace.create_file("RUNBOOK.md", "\n".join(lines), overwrite=True)
            return {"ok": True, "summary": "wrote RUNBOOK.md"}
        if name == "request_approval":
            item = self.gate.request(args["action"], args.get("detail", ""))
            return {"ok": True, "approval_id": item.id, "summary": f"{item.id} pending"}
        raise AssertionError("unreachable")
