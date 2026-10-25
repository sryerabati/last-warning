import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app import bedrock
from backend.app.bedrock import (
    CALL_RESERVATION,
    MODEL_ID,
    NANODOLLARS,
    BedrockError,
    BedrockPolicy,
    BudgetExceeded,
    DecisionValidationError,
    SpendLedger,
    agent_status,
    parse_decisions,
    response_excerpt,
)


def residents(count=3):
    return [{"id": i, "goal": "Reach shelter safely", "perceived_warning": "Leave now.",
             "available_actions": ["WAIT", "EVACUATE"], "route": {"available": True}}
            for i in range(count)]


class FakeClient:
    def __init__(self, response_text=None, stop_reason="end_turn", failure=None, response_for_context=None):
        self.calls = []
        self.lock = threading.Lock()
        self.response_text = response_text
        self.stop_reason = stop_reason
        self.failure = failure
        self.response_for_context = response_for_context

    def converse(self, **request):
        with self.lock:
            self.calls.append(request)
            number = len(self.calls)
        if self.failure:
            raise self.failure
        context = json.loads(request["messages"][0]["content"][0]["text"].split("\n")[0])
        text = json.dumps({"decisions": [{"id": r["id"], "action": "EVACUATE", "reason": "Follow the clear safe route"}
                                         for r in context["residents"]]})
        if self.response_text is not None:
            text = self.response_text(number)
        if self.response_for_context is not None:
            text = json.dumps(self.response_for_context(context, number))
        return {"output": {"message": {"content": [{"text": text}]}},
                "stopReason": self.stop_reason,
                "usage": {"inputTokens": 120, "outputTokens": 90},
                "ResponseMetadata": {"RequestId": f"actual-provider-request-{number}"}}


def test_real_provider_protocol_batches_exact_residents_and_records_usage(tmp_path):
    client = FakeClient()
    policy = BedrockPolicy(tmp_path, client=client)
    result = policy.decide(residents(41), {"text": "THIS MUST NOT LEAK TO UNALERTED AGENTS", "channels": ["mobile"]},
                           {"name": "Riverside", "tick_seconds": 5, "disaster_type": "flood",
                            "hazard_origin": [19, 4], "seed": 42}, 16)
    assert set(result) == set(range(41))
    assert all(decision.action == "EVACUATE" for decision in result.values())
    assert len(client.calls) == 5
    assert sorted(len(json.loads(c["messages"][0]["content"][0]["text"])["residents"]) for c in client.calls) == [1, 10, 10, 10, 10]
    assert all(c["modelId"] == MODEL_ID and c["inferenceConfig"]["maxTokens"] == 3000 for c in client.calls)
    assert all("THIS MUST NOT LEAK" not in c["messages"][0]["content"][0]["text"] for c in client.calls)
    usage = policy.usage
    assert usage["input_tokens"] == 600 and usage["output_tokens"] == 450
    assert usage["estimated_cost_usd"] == pytest.approx((600 * 35 + 450 * 140) / NANODOLLARS)
    assert usage["accounted_cost_usd"] == usage["estimated_cost_usd"]
    assert usage["decision_count"] == 41 and usage["rounds"] == 1
    assert len(usage["request_ids"]) == 5
    assert all(r["tick"] == 16 and len(r["context_sha256"]) == 64 for r in usage["requests"])
    assert SpendLedger(tmp_path).status()["estimated_cost_usd"] == usage["estimated_cost_usd"]
    for call in client.calls:
        payload = json.loads(call["messages"][0]["content"][0]["text"])
        assert payload["city"] == {"name": "Riverside", "tick_seconds": 5}
        assert "toolConfig" not in call and "additionalModelRequestFields" not in call


def test_distinct_policies_serialize_sdk_client_creation_and_network_requests(tmp_path, monkeypatch):
    import boto3

    monitor = {"active_factory": 0, "factory_peak": 0, "factories": 0,
               "active_network": 0, "network_peak": 0, "requests": 0}
    lock = threading.Lock()
    ready = threading.Barrier(2)

    class TrackingClient(FakeClient):
        def converse(self, **request):
            with lock:
                monitor["active_network"] += 1
                monitor["network_peak"] = max(monitor["network_peak"], monitor["active_network"])
                monitor["requests"] += 1
            try:
                time.sleep(.02)
                return super().converse(**request)
            finally:
                with lock:
                    monitor["active_network"] -= 1

    class Session:
        def client(self, name, **kwargs):
            assert name == "bedrock-runtime"
            assert kwargs.get("verify", True) is True
            assert kwargs["config"].max_pool_connections == 1
            with lock:
                monitor["active_factory"] += 1
                monitor["factories"] += 1
                monitor["factory_peak"] = max(monitor["factory_peak"], monitor["active_factory"])
            try:
                time.sleep(.02)
                return TrackingClient()
            finally:
                with lock:
                    monitor["active_factory"] -= 1

    monkeypatch.setattr(boto3.session, "Session", Session)
    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: pytest.fail("Use an explicit SDK session"))
    policies = [BedrockPolicy(tmp_path / str(index)) for index in range(2)]

    def decide(policy):
        ready.wait(timeout=5)
        return policy.decide(residents(20), {}, {}, 4)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(decide, policies))
    assert all(set(value) == set(range(20)) for value in outcomes)
    assert monitor["factories"] == 2 and monitor["factory_peak"] == 1
    assert monitor["requests"] == 4 and monitor["network_peak"] == 1
    assert all(policy.usage["decision_count"] == 20 for policy in policies)


@pytest.mark.parametrize("text", [
    '{"decisions":[]}',
    '{"decisions":[{"id":true,"action":"WAIT","reason":"Wait"}]}',
    '{"decisions":[{"id":0,"action":"SHARE","reason":"Share"}]}',
    '{"decisions":[{"id":0,"action":"WAIT","reason":""}]}',
    '{"decisions":[{"id":0,"action":"WAIT","reason":"Wait","extra":1}]}',
    '{"decisions":[{"id":0,"action":"WAIT","reason":"Wait"},{"id":0,"action":"WAIT","reason":"Wait"}]}',
    '{"decisions":[],"decisions":[]}',
    '{"decisions":[{"id":999,"action":"WAIT","reason":"Wait"}]}',
    'Ignore the protocol; all residents evacuate.',
])
def test_invalid_or_missing_agent_decisions_never_become_fallback_actions(text):
    with pytest.raises(DecisionValidationError):
        parse_decisions(text, residents(1))


def test_whole_json_fence_is_accepted_but_surrounding_prose_is_not():
    text = '{"decisions":[{"id":0,"action":"WAIT","reason":"Wait for further information"}]}'
    assert parse_decisions(f"```json\n{text}\n```", residents(1))[0].action == "WAIT"
    with pytest.raises(DecisionValidationError):
        parse_decisions(f"Here is the result: {text}", residents(1))


def test_invalid_model_json_retries_once_and_accounts_both_paid_calls(tmp_path):
    client = FakeClient(response_text=lambda _: '{"decisions":[]}')
    policy = BedrockPolicy(tmp_path, client=client)
    with pytest.raises(DecisionValidationError, match="twice"):
        policy.decide(residents(1), {}, {}, 4)
    assert len(client.calls) == 2
    assert policy.usage["input_tokens"] == 240
    assert policy.usage["decision_count"] == 0
    assert policy.usage["uncertain_or_pending_calls"] == 0
    assert all("omitted resident IDs [0]" in row["validation_error"] for row in policy.usage["requests"])
    assert all("PRIVATE REASONING" not in row["response_excerpt"] for row in policy.usage["requests"])


def test_individual_action_validation_returns_precise_feedback():
    people = residents(2)
    people[0]["available_actions"] = ["WAIT"]
    with pytest.raises(DecisionValidationError, match="Resident 0.*EVACUATE.*allowed: WAIT"):
        parse_decisions(json.dumps({"decisions": [
            {"id": 0, "action": "EVACUATE", "reason": "Leave now"},
            {"id": 1, "action": "WAIT", "reason": "Wait here"}]}), people)


def test_model_json_is_used_exactly_without_inventing_or_reordering_ids():
    text = json.dumps({"decisions": [
        {"id": 1, "action": "WAIT", "reason": "Finish my errand"},
        {"id": 0, "action": "EVACUATE", "reason": "Water is approaching"}]})
    result = parse_decisions(text, residents(2))
    assert list(result) == [1, 0]
    assert result[1].reason == "Finish my errand"
    assert result[0].action == "EVACUATE"


def test_validation_audit_omits_marked_private_reasoning():
    excerpt = response_excerpt([{"text": '<thinking>PRIVATE REASONING</thinking>{"decisions":[]}'}])
    assert "PRIVATE REASONING" not in excerpt
    assert '{"decisions":[]}' in excerpt


def test_truncated_model_output_is_not_applied(tmp_path):
    client = FakeClient(stop_reason="max_tokens")
    policy = BedrockPolicy(tmp_path, client=client)
    with pytest.raises(DecisionValidationError):
        policy.decide(residents(1), {}, {}, 4)
    assert len(client.calls) == 2


def test_run_budget_refuses_before_any_paid_call(tmp_path):
    client = FakeClient()
    policy = BedrockPolicy(tmp_path, client=client, max_run_usd=.001)
    with pytest.raises(BudgetExceeded):
        policy.decide(residents(1), {}, {}, 4)
    assert client.calls == []
    assert policy.usage["calls"] == 0


def test_atomic_phase_reservations_survive_restart_and_bound_concurrent_runs(tmp_path):
    ledger = SpendLedger(tmp_path, phase_cap_usd=.01)
    for number in range(3):
        ledger.register_run(str(number), .30)

    def reserve(number):
        try:
            return ledger.reserve(str(number))
        except BudgetExceeded:
            return None

    with ThreadPoolExecutor(max_workers=3) as pool:
        reserved = list(pool.map(reserve, range(3)))
    assert len([key for key in reserved if key]) == 2
    restarted = SpendLedger(tmp_path, phase_cap_usd=.01)
    assert restarted.usage()["accounted_cost_usd"] == pytest.approx(2 * CALL_RESERVATION / NANODOLLARS)
    assert restarted.usage()["uncertain_or_pending_calls"] == 2
    with pytest.raises(BudgetExceeded):
        restarted.reserve("2")


def test_network_failure_is_redacted_and_retains_conservative_charge(tmp_path):
    client = FakeClient(failure=RuntimeError("SENSITIVE PROVIDER RESPONSE OR AUTH HEADER"))
    policy = BedrockPolicy(tmp_path, client=client)
    with pytest.raises(BedrockError) as result:
        policy.decide(residents(1), {}, {}, 4)
    assert "SENSITIVE" not in str(result.value)
    assert len(client.calls) == 1
    assert policy.usage["estimated_cost_usd"] == 0
    assert policy.usage["accounted_cost_usd"] == CALL_RESERVATION / NANODOLLARS


def test_transient_timeout_retries_once_and_keeps_unknown_charge(tmp_path):
    from botocore.exceptions import ReadTimeoutError

    client = FakeClient(failure=ReadTimeoutError(endpoint_url="https://bedrock-runtime.us-east-2.amazonaws.com"))
    policy = BedrockPolicy(tmp_path, client=client)
    with pytest.raises(BedrockError, match="ReadTimeoutError"):
        policy.decide(residents(1), {}, {}, 4)
    assert len(client.calls) == 2
    assert policy.usage["estimated_cost_usd"] == 0
    assert policy.usage["accounted_cost_usd"] == 2 * CALL_RESERVATION / NANODOLLARS
    assert policy.usage["uncertain_or_pending_calls"] == 2


def test_invalid_action_retry_receives_feedback_and_uses_new_model_response(tmp_path):
    people = residents(1)
    people[0]["available_actions"] = ["WAIT"]
    client = FakeClient(response_text=lambda number: json.dumps({"decisions": [{
        "id": 0, "action": "EVACUATE" if number == 1 else "WAIT", "reason": "Continue my planned activity"}]}))
    policy = BedrockPolicy(tmp_path, client=client)
    result = policy.decide(people, {}, {}, 4)
    assert result[0].action == "WAIT"
    assert len(client.calls) == 2
    retry_prompt = client.calls[1]["messages"][0]["content"][0]["text"]
    assert "Resident 0" in retry_prompt and "allowed: WAIT" in retry_prompt
    assert policy.usage["input_tokens"] == 240


def test_incomplete_document_exposes_only_validated_partial_choices_and_exact_missing_ids():
    people = [{**value, "id": key} for value, key in zip(residents(3), [3, 17, 42], strict=True)]
    text = json.dumps({"decisions": [
        {"id": 17, "action": "WAIT", "reason": "Continue my planned activity"},
        {"id": 3, "action": "EVACUATE", "reason": "Water is approaching"}]})
    with pytest.raises(bedrock.IncompleteDecisions) as result:
        parse_decisions(text, people)
    assert set(result.value.missing) == {42}
    assert set(result.value.partial) == {3, 17}
    assert result.value.partial[3].action == "EVACUATE"
    assert result.value.partial[17].reason == "Continue my planned activity"
    assert "42" in str(result.value)


def test_nine_valid_choices_plus_one_missing_are_recovered_by_actual_model_response(tmp_path):
    def response(context, number):
        rows = context["residents"][:-1] if number == 1 else context["residents"]
        return {"decisions": [{"id": resident["id"], "action": "EVACUATE" if number == 1 else "WAIT",
                               "reason": "First model decision" if number == 1 else "Recovered model decision"}
                              for resident in rows]}

    client = FakeClient(response_for_context=response)
    policy = BedrockPolicy(tmp_path, client=client)
    result = policy.decide(residents(10), {}, {}, 4)
    assert set(result) == set(range(10))
    assert all(result[key].action == "EVACUATE" and result[key].reason == "First model decision"
               for key in range(9))
    assert result[9].action == "WAIT" and result[9].reason == "Recovered model decision"
    assert len(client.calls) == 2
    prompts = [json.loads(call["messages"][0]["content"][0]["text"].split("\n")[0]) for call in client.calls]
    assert prompts[0]["requested_resident_ids"] == list(range(10))
    assert prompts[1]["requested_resident_ids"] == [9]
    assert [resident["id"] for resident in prompts[1]["residents"]] == [9]
    assert policy.usage["input_tokens"] == 240 and policy.usage["output_tokens"] == 180
    assert policy.usage["decision_count"] == 10


def test_missing_retry_preserves_noncontiguous_resident_ids(tmp_path):
    people = [{**value, "id": key} for value, key in zip(residents(3), [140, 148, 150], strict=True)]

    def response(context, number):
        rows = context["residents"][:2] if number == 1 else context["residents"]
        return {"decisions": [{"id": resident["id"], "action": "WAIT", "reason": "Continue my planned activity"}
                              for resident in rows]}

    client = FakeClient(response_for_context=response)
    result = BedrockPolicy(tmp_path, client=client).decide(people, {}, {}, 4)
    assert set(result) == {140, 148, 150}
    second = json.loads(client.calls[1]["messages"][0]["content"][0]["text"].split("\n")[0])
    assert second["requested_resident_ids"] == [150]
    assert [resident["id"] for resident in second["residents"]] == [150]


def test_invalid_recovery_returns_no_partial_result_or_third_request(tmp_path):
    def response(context, number):
        if number == 1:
            return {"decisions": [{"id": resident["id"], "action": "WAIT", "reason": "Continue my planned activity"}
                                  for resident in context["residents"][:-1]]}
        return {"decisions": [{"id": context["residents"][0]["id"], "action": "FLY", "reason": "Invalid recovery"}]}

    client = FakeClient(response_for_context=response)
    policy = BedrockPolicy(tmp_path, client=client)
    with pytest.raises(DecisionValidationError):
        policy.decide(residents(10), {}, {}, 4)
    assert len(client.calls) == 2
    assert policy.usage["decision_count"] == 0 and policy.usage["rounds"] == 0
    assert policy.usage["input_tokens"] == 240


def test_invalid_row_and_missing_id_cannot_be_recovered_as_valid_partial_choices():
    text = json.dumps({"decisions": [{"id": 0, "action": "FLY", "reason": "Invalid action"}]})
    with pytest.raises(DecisionValidationError) as result:
        parse_decisions(text, residents(2))
    assert not isinstance(result.value, bedrock.IncompleteDecisions)
    assert result.value.partial == {}
    assert result.value.pending == {0, 1}


def test_validation_collects_all_bad_rows_and_missing_ids_without_retaining_them():
    rows = [
        {"id": 0, "action": "WAIT", "reason": "Wait here"},
        {"id": 1, "action": "SHARE", "reason": "Cannot share an unreceived warning"},
        {"id": 2, "action": "WAIT", "reason": ""},
    ]
    with pytest.raises(bedrock.InvalidResidentDecisions) as result:
        parse_decisions(json.dumps({"decisions": rows}), residents(4))
    assert set(result.value.partial) == {0}
    assert result.value.pending == {1, 2, 3}
    assert len(result.value.errors) == 3
    assert "Resident 1" in str(result.value) and "Resident 2" in str(result.value)
    assert "omitted resident IDs [3]" in str(result.value)


@pytest.mark.parametrize("extra", [
    {"id": 0, "action": "WAIT", "reason": "Duplicate invalid row"},
    {"id": 42, "action": "WAIT", "reason": "Unrequested row"},
    {"id": 1, "action": "WAIT", "reason": "Extra field", "extra": True},
])
def test_ambiguous_document_ownership_cannot_preserve_partial_rows(extra):
    rows = [{"id": 0, "action": "FLY", "reason": "Invalid choice"}, extra]
    with pytest.raises(DecisionValidationError) as result:
        parse_decisions(json.dumps({"decisions": rows}), residents(2))
    assert type(result.value) is DecisionValidationError


def test_campus_retry_repairs_only_invalid_dependents_without_corrupting_valid_choices(tmp_path):
    # Regression for the real tick-2 blizzard failure: retrying the entire batch
    # repaired residents 2/5 but changed unalerted resident 1 to forbidden SHARE.
    people = [{"id": key, "warning_received": key not in {0, 1},
               "perceived_warning": None if key in {0, 1} else "Blizzard warning",
               "available_actions": (["WAIT", "CONTINUE_ROUTINE", "PREPARE", "POSTPONE_TRAVEL"]
                                     if key in {0, 1} else ["SHARE", "STAY_WITH_GROUP"]
                                     if key in {2, 5} else ["SHARE", "SHELTER_IN_PLACE", "SEEK_INDOOR_SHELTER"])}
              for key in range(10)]
    first = [{"id": key, "action": action, "reason": reason} for key, action, reason in [
        (0, "CONTINUE_ROUTINE", "No credible warning"),
        (1, "CONTINUE_ROUTINE", "No warning received"),
        (2, "CONTINUE_ROUTINE", "No credible warning"),
        (3, "SHELTER_IN_PLACE", "Blizzard warning received"),
        (4, "SHELTER_IN_PLACE", "Blizzard warning received"),
        (5, "CONTINUE_ROUTINE", "No credible warning"),
        (6, "SEEK_INDOOR_SHELTER", "Blizzard observed nearby"),
        (7, "SEEK_INDOOR_SHELTER", "Blizzard observed nearby"),
        (8, "SHELTER_IN_PLACE", "Blizzard warning received"),
        (9, "SHELTER_IN_PLACE", "Blizzard warning received"),
    ]]

    def response(context, number):
        if number == 1:
            assert len(context["decision_constraints"]) == 10
            return {"decisions": first}
        assert context["requested_resident_ids"] == [2, 5]
        assert [row["id"] for row in context["residents"]] == [2, 5]
        assert context["decision_constraints"] == [
            {"id": key, "choose_one_of": ["SHARE", "STAY_WITH_GROUP"]} for key in (2, 5)]
        return {"decisions": [{"id": key, "action": "STAY_WITH_GROUP", "reason": "Stay with household leader"}
                              for key in (2, 5)]}

    client = FakeClient(response_for_context=response)
    policy = BedrockPolicy(tmp_path, client=client)
    result = policy.decide(people, {}, {"layout": "campus", "town_life": True}, 2)
    assert set(result) == set(range(10))
    for row in first:
        if row["id"] not in {2, 5}:
            assert result[row["id"]] == bedrock.Decision(row["action"], row["reason"])
    assert result[2].action == result[5].action == "STAY_WITH_GROUP"
    retry = client.calls[1]["messages"][0]["content"][0]["text"]
    assert "Resident 2" in retry and "Resident 5" in retry
    assert policy.usage["decision_protocol"] == "nova_resident_json_campus_v3"
    assert len(client.calls) == 2 and policy.usage["decision_count"] == 10
    assert policy.usage["input_tokens"] == 240 and policy.usage["output_tokens"] == 180
    assert policy.usage["accounted_cost_usd"] == policy.usage["estimated_cost_usd"]


def test_invalid_subset_retry_cannot_overwrite_accepted_resident_or_send_third_request(tmp_path):
    def response(context, number):
        if number == 1:
            return {"decisions": [
                {"id": 0, "action": "WAIT", "reason": "Stay here"},
                {"id": 1, "action": "SHARE", "reason": "Invalid choice"}]}
        assert context["requested_resident_ids"] == [1]
        return {"decisions": [{"id": 0, "action": "EVACUATE", "reason": "Unrequested revision"},
                              {"id": 1, "action": "WAIT", "reason": "Remain here"}]}

    client = FakeClient(response_for_context=response)
    policy = BedrockPolicy(tmp_path, client=client)
    with pytest.raises(DecisionValidationError, match="twice"):
        policy.decide(residents(2), {}, {}, 4)
    assert len(client.calls) == 2
    assert policy.usage["decision_count"] == 0 and policy.usage["rounds"] == 0
    assert policy.usage["input_tokens"] == 240


def test_failed_recovery_never_applies_partial_round_to_mesa_residents(tmp_path):
    from backend.app.schemas import GENERIC, ScenarioConfig
    from backend.app.simulation.engine import Simulation

    def response(context, number):
        if number == 1:
            return {"decisions": [{"id": resident["id"], "action": "EVACUATE", "reason": "Leave by the available route"}
                                  for resident in context["residents"][:-1]]}
        return {"decisions": [{"id": context["residents"][0]["id"], "action": "FLY", "reason": "Invalid recovery"}]}

    client = FakeClient(response_for_context=response)
    policy = BedrockPolicy(tmp_path, client=client)
    simulation = Simulation(ScenarioConfig(population=10, decision_mode="bedrock", hazard_spread=.1),
                            GENERIC, decision_policy=policy)
    for _ in range(4):
        simulation.step()
    positions = [resident.position for resident in simulation.people]
    with pytest.raises(DecisionValidationError):
        simulation.step()
    assert all(not resident.model_decisions for resident in simulation.people)
    assert [resident.position for resident in simulation.people] == positions
    assert not any(event["type"] == "agent_model_decision" for event in simulation.events)
    assert len(client.calls) == 2


def test_expired_credentials_are_not_retried_or_charged(tmp_path):
    class Expired(Exception):
        def __init__(self):
            self.response = {"Error": {"Code": "ExpiredTokenException", "Message": "secret"}}

    client = FakeClient(failure=Expired())
    policy = BedrockPolicy(tmp_path, client=client)
    with pytest.raises(BedrockError, match="ExpiredTokenException"):
        policy.decide(residents(1), {}, {}, 4)
    assert len(client.calls) == 1
    assert policy.usage["accounted_cost_usd"] == 0


def test_model_service_diagnostics_keep_request_id_but_exclude_headers(tmp_path):
    class ModelFailure(Exception):
        def __init__(self):
            self.response = {"Error": {"Code": "ModelErrorException", "Message": "Invalid tool sequence"},
                             "originalStatusCode": 424, "originalMessage": "Decoder rejected tool arguments",
                             "ResponseMetadata": {"RequestId": "aws-error-request-id",
                                 "HTTPHeaders": {"authorization": "SECRET AUTH HEADER"}}}

    policy = BedrockPolicy(tmp_path, client=FakeClient(failure=ModelFailure()))
    with pytest.raises(BedrockError) as result:
        policy.decide(residents(1), {}, {}, 4)
    assert "Invalid tool sequence" not in str(result.value)
    request = policy.usage["requests"][0]
    assert request["request_id"] == "aws-error-request-id"
    assert request["state"] == "uncertain"
    assert "Invalid tool sequence" in request["validation_error"]
    diagnostic = json.loads(request["response_excerpt"])
    assert diagnostic["original_status_code"] == 424
    assert diagnostic["original_message"] == "Decoder rejected tool arguments"
    assert "SECRET AUTH HEADER" not in request["response_excerpt"]


def test_status_is_local_and_has_no_paid_calls_or_run_reservations(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.app.bedrock.importlib.util.find_spec", lambda _: None)
    result = agent_status(tmp_path)
    assert result["available"] is False
    assert result["budget"]["calls"] == 0
    assert result["budget"]["project_accounted_cost_usd"] == .00000441
    assert result["authentication_verified"] is False
    assert result["max_run_usd"] == .30


def test_status_checks_local_sdk_credentials_without_metadata_or_inference(tmp_path, monkeypatch):
    import boto3

    removed = []

    class Resolver:
        def remove(self, name):
            removed.append(name)

    class Session:
        _session = None

        def __init__(self, **_):
            self._session = self

        def get_component(self, name):
            assert name == "credential_provider"
            return Resolver()

        def get_credentials(self):
            assert removed == ["iam-role", "container-role"]
            return object()

    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
    monkeypatch.setattr(boto3, "Session", Session)
    result = agent_status(tmp_path)
    assert result["available"] is True
    assert result["authentication_verified"] is False
    assert result["spent_usd"] == 0 and result["remaining_usd"] == 5
    assert result["budget"]["calls"] == 0


@pytest.mark.parametrize("kwargs", [{"max_run_usd": .31}, {"phase_cap_usd": 5.1},
                                     {"max_run_usd": float("nan")}, {"model_id": "more-expensive-model"},
                                     {"region": "ap-northeast-1"}])
def test_unpriced_models_regions_or_looser_budgets_are_rejected(tmp_path, kwargs):
    with pytest.raises(ValueError):
        BedrockPolicy(tmp_path, client=FakeClient(), **kwargs)
