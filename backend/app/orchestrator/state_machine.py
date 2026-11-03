"""Genesis orchestrator states. Persistent state machine contract."""

from enum import Enum


class RunState(str, Enum):
    CREATED = "CREATED"
    SPECIFICATION = "SPECIFICATION"
    PLANNING = "PLANNING"
    ARCHITECTURE = "ARCHITECTURE"
    IMPLEMENTATION = "IMPLEMENTATION"
    EXECUTION = "EXECUTION"
    TESTING = "TESTING"
    DIAGNOSIS = "DIAGNOSIS"
    REPAIR = "REPAIR"
    REGRESSION = "REGRESSION"
    REVIEW = "REVIEW"
    VERIFICATION = "VERIFICATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    CANCELLED = "CANCELLED"


ALLOWED_TRANSITIONS: dict[RunState, set[RunState]] = {
    RunState.CREATED: {RunState.SPECIFICATION, RunState.CANCELLED},
    RunState.SPECIFICATION: {RunState.PLANNING, RunState.FAILED, RunState.CANCELLED},
    RunState.PLANNING: {RunState.ARCHITECTURE, RunState.FAILED, RunState.CANCELLED},
    RunState.ARCHITECTURE: {RunState.IMPLEMENTATION, RunState.FAILED, RunState.CANCELLED},
    RunState.IMPLEMENTATION: {RunState.EXECUTION, RunState.WAITING_FOR_APPROVAL, RunState.FAILED},
    RunState.EXECUTION: {RunState.TESTING, RunState.DIAGNOSIS, RunState.FAILED},
    RunState.TESTING: {RunState.VERIFICATION, RunState.REVIEW, RunState.DIAGNOSIS, RunState.FAILED},
    RunState.DIAGNOSIS: {RunState.REPAIR, RunState.FAILED},
    RunState.REPAIR: {RunState.REGRESSION, RunState.FAILED, RunState.WAITING_FOR_APPROVAL},
    RunState.REGRESSION: {RunState.VERIFICATION, RunState.DIAGNOSIS, RunState.FAILED},
    RunState.REVIEW: {RunState.VERIFICATION, RunState.FAILED},
    RunState.VERIFICATION: {RunState.COMPLETED, RunState.FAILED},
    RunState.WAITING_FOR_APPROVAL: {RunState.IMPLEMENTATION, RunState.REPAIR, RunState.CANCELLED},
    RunState.COMPLETED: set(),
    RunState.FAILED: set(),
    RunState.CANCELLED: set(),
}


def can_transition(frm: RunState, to: RunState) -> bool:
    return to in ALLOWED_TRANSITIONS.get(frm, set())
