"""Intelligence layer: registry, prompts, tracked client, router."""

from app.intelligence.meta_client import MetaClient, MetaConfig
from app.intelligence.model_registry import ModelRegistry
from app.intelligence.model_router import ModelRouter
from app.intelligence.prompt_manager import get_prompt, render


def test_registry_summary_math():
    reg = ModelRegistry()
    reg.record.__self__  # registry is usable
    from app.intelligence.model_registry import ModelCall
    reg.record(ModelCall(id="a", model="muse-spark-1.3", task="t", latency_ms=100, ok=True))
    reg.record(ModelCall(id="b", model="muse-spark-1.3", task="t", latency_ms=300, ok=False, error="x"))
    s = reg.summary()
    assert s == {"total": 2, "ok": 1, "errors": 1, "avg_latency_ms": 200,
                 "by_model": {"muse-spark-1.3": 2}}
    assert [c.id for c in reg.last(1)] == ["b"]


def test_missing_key_records_call_with_request_id():
    reg = ModelRegistry()
    client = MetaClient(MetaConfig(api_key="", base_url="https://api.meta.ai/v1",
                                   primary_model="muse-spark-1.3",
                                   advanced_model="muse-wonder-1.0"), registry=reg)
    res = client.respond("muse-spark-1.3", "hi", task="unit")
    assert res["ok"] is False and "MODEL_API_KEY" in res["error"]
    (call,) = reg.calls
    assert call.model == "muse-spark-1.3" and call.task == "unit"
    assert call.id.startswith("req-")


def test_prompt_versioning_and_render():
    version, template = get_prompt("spec.extract")
    assert version == "v1" and "{spec}" in template
    _, text = render("spec.extract", {"spec": "do things"})
    assert "do things" in text
    try:
        render("spec.extract", {"wrong": "x"})
    except KeyError:
        pass
    else:
        raise AssertionError("missing variable must raise")
    try:
        get_prompt("nope")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown prompt must raise")


def test_build_payload_agentic_knobs():
    client = MetaClient(MetaConfig(api_key="", base_url="https://api.meta.ai/v1",
                                   primary_model="muse-spark-1.3",
                                   advanced_model="muse-wonder-1.0"))
    minimal = client.build_payload("muse-spark-1.3", "hi")
    assert minimal == {"model": "muse-spark-1.3", "input": "hi"}
    full = client.build_payload(
        "muse-wonder-1.0", "plan this",
        tools=[{"type": "function", "name": "read_file"}],
        response_format={"type": "json_schema", "name": "plan"},
        effort="high", stream=True)
    assert full["tools"][0]["name"] == "read_file"
    assert full["response_format"]["name"] == "plan"
    assert full["reasoning"] == {"effort": "high"}
    assert full["stream"] is True
    assert full["model"] == "muse-wonder-1.0"  # never swapped


def test_router_never_hardcodes_and_routes():
    client = MetaClient(MetaConfig(api_key="", base_url="https://api.meta.ai/v1",
                                   primary_model="muse-spark-1.3",
                                   advanced_model="muse-wonder-1.0"))
    router = ModelRouter(client)
    assert router.pick_model("routine codegen") == "muse-spark-1.3"
    assert router.pick_model("complex architecture planning") == "muse-wonder-1.0"
    res = router.run("routine codegen", "hi")
    assert res["model"] == "muse-spark-1.3" and res["ok"] is False
