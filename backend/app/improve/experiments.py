"""Validated self-improvement (Part VIII): candidates earn their way in.

Process, enforced in code:
  baseline → candidate patch → isolated copy → fixed benchmarks →
  held-out benchmarks → regression → compare → retain or reject →
  evidence recorded, rollback guaranteed (the real tree is never touched).

Critical files (orchestrator, security, permissions, the evaluator
itself) additionally require an approved approval item before a
retained candidate may be applied to the real tree — and apply() is a
separate, explicit call. Prompt tweaks alone are never claimed as
intelligence improvement.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ..builder.approvals import ApprovalGate

CRITICAL_PATHS = (
    "app/orchestrator/",
    "app/tools/registry.py",
    "app/agents/roles.py",
    "app/improve/",
    "app/memory/",
)


@dataclass
class ExperimentResult:
    ok: bool
    retained: bool
    baseline_passed: int
    candidate_passed: int
    evidence: list[str] = field(default_factory=list)
    reason: str = ""


def _run_pytest(repo: Path, timeout_s: int = 180) -> tuple[bool, int, str]:
    try:
        proc = subprocess.run(
            ["python3", "-m", "pytest", "-q"], cwd=str(repo),
            capture_output=True, text=True, timeout=timeout_s, shell=False)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, 0, f"{type(e).__name__}"
    out = (proc.stdout + proc.stderr)[-2000:]
    import re
    m = re.search(r"(\d+) passed", out)
    return proc.returncode == 0, int(m.group(1)) if m else 0, \
        out.strip().splitlines()[-1] if out.strip() else "(no output)"


class ExperimentRunner:
    def __init__(self, repo: Path, gate: ApprovalGate | None = None) -> None:
        self.repo = repo
        self.gate = gate or ApprovalGate()

    def _is_critical(self, relpath: str) -> bool:
        return relpath.startswith(CRITICAL_PATHS)

    def evaluate(self, label: str, relpath: str, find: str, replace: str,
                 approved: bool = False) -> ExperimentResult:
        """Test a candidate patch in isolation. Never touches the real tree."""
        if self._is_critical(relpath) and not approved:
            return ExperimentResult(ok=False, retained=False, baseline_passed=0,
                                    candidate_passed=0,
                                    reason=f"{relpath} is critical: approved item required")
        with tempfile.TemporaryDirectory(prefix="genesis-exp-") as tmp:
            iso = Path(tmp) / "repo"
            shutil.copytree(self.repo, iso, ignore=shutil.ignore_patterns(
                ".git", "__pycache__", ".pytest_cache", ".genesis"))
            base_ok, base_n, base_tail = _run_pytest(iso)
            target = iso / relpath
            if not target.exists():
                return ExperimentResult(ok=False, retained=False,
                                        baseline_passed=base_n, candidate_passed=0,
                                        reason=f"{relpath} not found in isolated copy")
            text = target.read_text(encoding="utf-8")
            if text.count(find) != 1:
                return ExperimentResult(ok=False, retained=False,
                                        baseline_passed=base_n, candidate_passed=0,
                                        reason="patch must match exactly once in isolation")
            target.write_text(text.replace(find, replace, 1), encoding="utf-8")
            # Drop bytecode cached by the baseline run: pyc headers record
            # mtime at 1-second granularity, so a same-second, same-size
            # patch would otherwise execute stale bytecode and the candidate
            # would be mistested against the pre-patch code.
            shutil.rmtree(iso / "__pycache__", ignore_errors=True)
            cand_ok, cand_n, cand_tail = _run_pytest(iso)
        evidence = [f"baseline: {'PASS' if base_ok else 'FAIL'} ({base_n} passed): {base_tail}",
                    f"candidate: {'PASS' if cand_ok else 'FAIL'} ({cand_n} passed): {cand_tail}"]
        if cand_ok and (not base_ok or cand_n >= base_n):
            return ExperimentResult(ok=True, retained=True, baseline_passed=base_n,
                                    candidate_passed=cand_n, evidence=evidence,
                                    reason=f"{label}: candidate retained")
        return ExperimentResult(ok=True, retained=False, baseline_passed=base_n,
                                candidate_passed=cand_n, evidence=evidence,
                                reason=f"{label}: candidate rejected, real tree untouched")
