"""Proves the Meta Model API connection path.

- Without MODEL_API_KEY: passes as skipped (reports config state, asserts
  the client returns an informative error instead of crashing).
- With MODEL_API_KEY: performs live GET /models and asserts a real response.
"""

import os

import pytest

from app.intelligence.meta_client import MetaClient, MetaConfig
from app.intelligence.model_router import ModelRouter
from app.orchestrator.state_machine import RunState, can_transition
from app.sandbox.exec import run_guarded
from app.spec.engine import parse_specification


def test_state_machine_contract():
    assert can_transition(RunState.CREATED, RunState.SPECIFICATION)
    assert not can_transition(RunState.CREATED, RunState.COMPLETED)


def test_spec_engine_splits_requirements():
    reqs = parse_specification("Users can log in securely. Users can create projects.")
    assert len(reqs) == 2
    assert reqs[0].id == "REQ-001"
    assert reqs[0].priority == "P0"


def test_router_picks_models_from_env():
    client = MetaClient(MetaConfig(api_key="", base_url="https://api.meta.ai/v1",
                                   primary_model="muse-spark-1.3",
                                   advanced_model="muse-wonder-1.0"))
    router = ModelRouter(client)
    assert router.pick_model("routine codegen") == "muse-spark-1.3"
    assert router.pick_model("complex architecture planning") == "muse-wonder-1.0"


def test_guarded_exec_captures_output():
    res = run_guarded(["python3", "-c", "print('genesis-ok')"])
    assert res["ok"] and "genesis-ok" in res["stdout"]


@pytest.mark.skipif(not os.environ.get("MODEL_API_KEY"),
                    reason="MODEL_API_KEY not set; live check skipped")
def test_meta_connectivity_live():
    result = MetaClient().check_connectivity()
    assert result["ok"], f"Meta API unreachable: {result.get('error')}"


def test_meta_missing_key_returns_informative_error():
    if os.environ.get("MODEL_API_KEY"):
        pytest.skip("key is set; error-path test not applicable")
    result = MetaClient().check_connectivity()
    assert result["ok"] is False
    assert "MODEL_API_KEY" in result["error"]
