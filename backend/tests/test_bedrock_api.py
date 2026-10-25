"""HTTP integration with isolated model doubles; these tests do not contact AWS."""
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.bedrock import BedrockError, BudgetExceeded, Decision, DecisionValidationError


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "AGENT_BUDGET_ROOT", tmp_path / "shared-budget")
    with TestClient(main.create_app(tmp_path / "app")) as value:
        yield value


def configure_bedrock(client):
    scenario = client.get("/api/scenarios/riverside").json()
    fields = {key: value for key, value in scenario.items() if key in main.ScenarioConfig.model_fields}
    fields.update(population=10, duration_ticks=12, decision_mode="bedrock")
    assert client.put("/api/scenarios/riverside", json=fields).status_code == 200
    return fields


def test_bedrock_preview_never_constructs_a_cloud_policy(client, monkeypatch):
    fields = configure_bedrock(client)

    def unexpected(*args, **kwargs):
        raise AssertionError("Geometry preview must not access a model")

    monkeypatch.setattr(main, "BedrockPolicy", unexpected)
    response = client.post("/api/scenarios/preview", json=fields)
    assert response.status_code == 200
    assert len(response.json()["frame"]["agents"]) == 10


def test_bedrock_decisions_survive_saved_recording_and_replay(client, monkeypatch):
    configure_bedrock(client)

    class Policy:
        usage: ClassVar[dict] = {"provider": "test_double", "model_id": "isolated-test", "calls": 1,
                 "input_tokens": 100, "output_tokens": 30, "estimated_cost_usd": .0000077}

        def __init__(self, root):
            assert root == main.AGENT_BUDGET_ROOT

        def decide(self, residents, warning, scenario, tick):
            return {resident["id"]: Decision("EVACUATE", "Test policy action") for resident in residents}

    monkeypatch.setattr(main, "BedrockPolicy", Policy)
    response = client.post("/api/runs", json={"scenario_id": "riverside", "warning_id": "generic"})
    assert response.status_code == 201
    run = response.json()
    assert run["decision_mode"] == "bedrock"
    assert run["agent_policy"]["decision_count"] == 10
    assert run["agent_policy"]["usage"]["model_id"] == "isolated-test"
    frames = client.get(f"/api/runs/{run['id']}/frames").json()["frames"]
    assert frames[0]["agent_decisions"] == []
    assert len(frames[4]["agent_decisions"]) == 10
    assert {value["reason"] for value in frames[4]["agent_decisions"]} == {"Test policy action"}
    events = client.get(f"/api/runs/{run['id']}/events").json()
    assert len([value for value in events if value["type"] == "agent_model_decision"]) == 10


@pytest.mark.parametrize("error,status", [(BedrockError, 503), (BudgetExceeded, 429),
                                        (DecisionValidationError, 502)])
def test_model_failure_stops_without_saving_a_rules_run(client, monkeypatch, error, status):
    configure_bedrock(client)

    class Policy:
        def __init__(self, root):
            pass

        def decide(self, *args):
            raise error("Explicit test provider failure")

    monkeypatch.setattr(main, "BedrockPolicy", Policy)
    response = client.post("/api/runs", json={"scenario_id": "riverside", "warning_id": "generic"})
    assert response.status_code == status
    assert response.json()["detail"] == "Explicit test provider failure"
    assert client.get("/api/runs").json() == []


def test_agent_status_does_not_make_a_model_call(client, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Status cannot create a policy")

    monkeypatch.setattr(main, "BedrockPolicy", unexpected)
    response = client.get("/api/agents/status")
    assert response.status_code == 200
    assert response.json()["model_id"] == "us.amazon.nova-micro-v1:0"
    assert response.json()["budget"]["calls"] == 0


def test_comparison_rejects_a_changed_model_decision_protocol(client, monkeypatch):
    configure_bedrock(client)

    class Policy:
        usage: ClassVar[dict] = {"provider": "test_double", "model_id": "isolated-test", "region": "test-region",
                 "decision_protocol": "first-protocol"}

        def __init__(self, root):
            pass

        def decide(self, residents, *args):
            return {resident["id"]: Decision("WAIT", "Test policy action") for resident in residents}

    monkeypatch.setattr(main, "BedrockPolicy", Policy)
    baseline = client.post("/api/runs", json={"scenario_id": "riverside", "warning_id": "generic"}).json()
    Policy.usage = {**Policy.usage, "decision_protocol": "different-protocol"}
    alternative = client.post("/api/runs", json={"scenario_id": "riverside", "warning_id": "actionable",
                                               "baseline_run_id": baseline["id"]}).json()
    assert baseline["initial_conditions_hash"] == alternative["initial_conditions_hash"]
    response = client.post("/api/comparisons", json={"baseline_run_id": baseline["id"],
                                                   "alternative_run_id": alternative["id"]})
    assert response.status_code == 422
    assert "same Bedrock model and decision protocol" in response.json()["detail"]
