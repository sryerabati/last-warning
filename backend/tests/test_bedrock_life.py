"""Living-town choices must remain actual, eligible provider output."""
import json

import pytest

from backend.app.bedrock import (
    DECISION_PROTOCOL,
    LIFE_DECISION_PROTOCOL,
    SYSTEM_PROMPT,
    BedrockPolicy,
    DecisionValidationError,
    parse_decisions,
)


def person(key=0, actions=None):
    return {"id": key, "goal": "Walk to the market, then return to my household",
            "perceived_warning": None,
            "town_life": {"home_id": "home-3", "activity": "shopping", "inside": False},
            "available_actions": actions or ["WAIT", "CONTINUE_ROUTINE"]}


def document(key=0, action="CONTINUE_ROUTINE"):
    return {"decisions": [{"id": key, "action": action, "reason": "Finish my market visit"}]}


class RecordingClient:
    def __init__(self, respond=None):
        self.calls = []
        self.respond = respond

    def converse(self, **request):
        self.calls.append(request)
        context = json.loads(request["messages"][0]["content"][0]["text"].split("\n")[0])
        if self.respond:
            result = self.respond(context, len(self.calls))
        else:
            result = {"decisions": [document(r["id"])["decisions"][0] for r in context["residents"]]}
        return {"output": {"message": {"content": [{"text": json.dumps(result)}]}},
                "stopReason": "end_turn", "usage": {"inputTokens": 100, "outputTokens": 30},
                "ResponseMetadata": {"RequestId": f"life-test-{len(self.calls)}"}}


def test_continue_requires_living_protocol_and_an_individual_available_action():
    text = json.dumps(document())
    assert parse_decisions(text, [person()], allow_routine=True)[0].action == "CONTINUE_ROUTINE"
    with pytest.raises(DecisionValidationError, match="unavailable action"):
        parse_decisions(text, [person()])
    with pytest.raises(DecisionValidationError, match="allowed: WAIT"):
        parse_decisions(text, [person(actions=["WAIT"])], allow_routine=True)


def test_life_provider_preserves_routine_context_bounded_knowledge_and_actual_choices(tmp_path):
    client = RecordingClient()
    policy = BedrockPolicy(tmp_path, client=client)
    residents = [person(2), person(9)]
    result = policy.decide(residents, {"text": "UNSEEN WARNING MUST NOT LEAK", "channels": ["mobile"]},
                           {"town_life": True, "name": "Riverside", "tick_seconds": 5}, 4)
    assert set(result) == {2, 9}
    assert all(value.action == "CONTINUE_ROUTINE" for value in result.values())
    assert all(value.reason == "Finish my market visit" for value in result.values())
    request = client.calls[0]
    payload = json.loads(request["messages"][0]["content"][0]["text"])
    assert payload["residents"] == residents
    assert "UNSEEN WARNING" not in request["messages"][0]["content"][0]["text"]
    assert "CONTINUE_ROUTINE follows" in request["system"][0]["text"]
    assert "WAIT holds position" in request["system"][0]["text"]
    assert policy.usage["decision_protocol"] == LIFE_DECISION_PROTOCOL
    assert policy.usage["decision_count"] == 2 and policy.usage["rounds"] == 1
    assert policy.usage["calls"] == 1 and policy.usage["input_tokens"] == 100


def test_missing_life_resident_still_requires_a_second_model_choice(tmp_path):
    def respond(context, number):
        ids = [r["id"] for r in context["residents"]]
        assert ids == ([2, 9] if number == 1 else [9])
        return document(ids[0])

    client = RecordingClient(respond)
    policy = BedrockPolicy(tmp_path, client=client)
    result = policy.decide([person(2), person(9)], {}, {"town_life": True}, 4)
    assert set(result) == {2, 9} and len(client.calls) == 2
    assert policy.usage["calls"] == 2
    assert policy.usage["decision_count"] == 2


def test_legacy_provider_rejects_routine_output_without_fallback(tmp_path):
    client = RecordingClient()
    policy = BedrockPolicy(tmp_path, client=client)
    with pytest.raises(DecisionValidationError, match="twice"):
        policy.decide([person()], {}, {"town_life": False}, 4)
    assert len(client.calls) == 2
    assert all(call["system"] == [{"text": SYSTEM_PROMPT}] for call in client.calls)
    assert policy.usage["decision_protocol"] == DECISION_PROTOCOL
    assert policy.usage["decision_count"] == 0
    assert policy.usage["calls"] == 2


def test_policy_cannot_mix_life_and_legacy_experiments(tmp_path):
    client = RecordingClient()
    policy = BedrockPolicy(tmp_path, client=client)
    policy.decide([person()], {}, {"town_life": True}, 4)
    with pytest.raises(DecisionValidationError, match="cannot mix"):
        policy.decide([person()], {}, {}, 16)
    assert len(client.calls) == 1
    assert policy.usage["decision_protocol"] == LIFE_DECISION_PROTOCOL
