"""Genesis end-to-end runner: the tool itself.

Usage:
    python3 -m app.run --spec "Users can log in. Users manage tasks." --workdir /tmp/demo

Pipeline (every step executed, nothing claimed):
    SPEC → Architect (requirements) → Builder (scaffold) →
    Testing (real pytest) → Reviewer (secrets + tests-present) → REPORT.

Exit code 0 only when tests pass AND review is clean. Untested
requirements are reported as UNTESTED, never as passed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.roles import (ArchitectAgent, BuilderAgent, DebuggerAgent, ReviewerAgent,
                              TestingAgent)
from app.builder.files import GenesisWorkspace
from app.orchestrator.state_machine import RunState, can_transition


def run_pipeline(spec: str, workdir: Path) -> dict:
    report: dict = {"states": [], "agents": {}, "verdict": "FAILED"}

    def goto(state: RunState) -> None:
        prev = RunState[report["states"][-1]] if report["states"] else RunState.CREATED
        assert can_transition(prev, state), f"illegal transition {prev} -> {state}"
        report["states"].append(state.value)

    goto(RunState.SPECIFICATION)
    arch = ArchitectAgent().run(spec)
    report["agents"]["architect"] = {"ok": arch.ok, "summary": arch.summary}
    if not arch.ok:
        report["verdict"] = "BLOCKED"
        report["reason"] = arch.summary
        return report

    goto(RunState.PLANNING)
    goto(RunState.ARCHITECTURE)
    goto(RunState.IMPLEMENTATION)
    ws = GenesisWorkspace(workdir)
    build = BuilderAgent(ws).scaffold(arch.data["requirements"])
    report["agents"]["builder"] = {"ok": build.ok, "summary": build.summary,
                                   "files": build.data.get("files", [])}

    goto(RunState.EXECUTION)
    goto(RunState.TESTING)
    test = TestingAgent().run(workdir)
    report["agents"]["testing"] = {"ok": test.ok, "summary": test.summary,
                                   "data": test.data}

    goto(RunState.REVIEW)
    review = ReviewerAgent().run(workdir)
    report["agents"]["reviewer"] = {"ok": review.ok, "summary": review.summary,
                                    "findings": review.data.get("findings", [])}

    if not test.ok:
        goto(RunState.DIAGNOSIS)
        diag = DebuggerAgent().run({"id": "F-001", "category": "test-failure",
                                    "logs": "\n".join(test.evidence),
                                    "files": build.data.get("files", [])})
        report["agents"]["debugger"] = {"ok": diag.ok, "summary": diag.summary,
                                       "diagnosis": diag.data}
        report["verdict"] = "FAILED"
        report["reason"] = test.summary
        return report

    goto(RunState.VERIFICATION)
    if not review.ok:
        report["verdict"] = "BLOCKED"
        report["reason"] = review.summary
    else:
        goto(RunState.COMPLETED)
        report["verdict"] = "VERIFIED"
        report["reason"] = f"{test.data.get('passed', 0)} test(s) passed, review clean."
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Genesis end-to-end run")
    parser.add_argument("--spec", required=True, help="Natural-language specification")
    parser.add_argument("--workdir", required=True, help="Empty working directory")
    args = parser.parse_args()
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    report = run_pipeline(args.spec, workdir)
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
