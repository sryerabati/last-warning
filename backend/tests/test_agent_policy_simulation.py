"""Model decisions govern behavior; simulation physics remain authoritative.

The fake policy replaces only the paid provider boundary. It is never used by
the application's actual Bedrock path or persisted as a real model response.
"""
import copy
from dataclasses import dataclass

import networkx as nx
import pytest

from backend.app.schemas import GENERIC, ScenarioConfig
from backend.app.simulation import Simulation, simulate
from backend.app.simulation.engine import MODEL_DECISION_TICKS, STATES
from backend.app.simulation.world import make_city


@dataclass
class Decision:
    action: str
    reason: str = "Test policy chose this action from the supplied resident context."


class Policy:
    def __init__(self, choose=lambda context, tick: "EVACUATE"):
        self.choose = choose
        self.calls = []
        self.usage = {"provider": "test-only", "model_id": "test-policy", "calls": 0,
                      "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0}

    def decide(self, residents, warning, scenario, tick):
        self.calls.append(copy.deepcopy({"residents": residents, "warning": warning, "scenario": scenario, "tick": tick}))
        self.usage["calls"] += 1
        return {r["id"]: Decision(self.choose(r, tick)) for r in residents}


def config(**updates):
    return ScenarioConfig(decision_mode="bedrock", population=30, duration_ticks=80, **updates)


def test_missing_policy_fails_instead_of_falling_back_to_rules():
    with pytest.raises(ValueError, match="no rule fallback"):
        simulate(config(), GENERIC)


def test_bedrock_rejects_rule_probability_coupling():
    with pytest.raises(ValueError, match="rule-based"):
        simulate(config(), GENERIC, notice_adjustment=0.1, decision_policy=Policy())


def test_rules_remain_the_backward_compatible_default_and_never_call_the_policy():
    policy = Policy()
    old = simulate(ScenarioConfig(population=20, duration_ticks=12), GENERIC, decision_policy=policy)
    assert old["decision_mode"] == "rules"
    assert old["agent_policy"]["usage"] is None
    assert old["agent_policy"]["decision_count"] == 0
    assert policy.calls == []


def test_model_evacuation_bypasses_notice_action_and_preparation_rules():
    warning = GENERIC.model_copy(update={"delivery_reach_probability": 1, "notice_probability": 0,
        "action_probability": 0, "response_delay": 120, "channels": ["mobile"]})
    policy = Policy()
    result = simulate(config(), warning, decision_policy=policy)
    starts = [e for e in result["events"] if e["type"] == "agent_started_evacuating"]
    assert starts and all(e["tick"] == 4 and e["decided_by"] == "bedrock" for e in starts)
    assert result["metrics"]["warning_noticed"] > 0
    assert result["metrics"]["evacuated"] > 0
    assert result["decision_mode"] == "bedrock"
    assert result["agent_policy"]["decision_count"] == sum(len(c["residents"]) for c in policy.calls)
    assert result["agent_policy"]["usage"]["model_id"] == "test-policy"
    assert result["agent_policy"]["decision_ticks"] == [c["tick"] for c in policy.calls]
    assert set(result["agent_policy"]["decision_ticks"]) <= set(MODEL_DECISION_TICKS)


def test_wait_does_not_turn_into_rule_based_evacuation_even_when_hazard_approaches():
    warning = GENERIC.model_copy(update={"channels": [], "notice_probability": 1, "action_probability": 1,
                                         "response_delay": 0, "social_share_probability": 1})
    result = simulate(config(), warning, decision_policy=Policy(lambda context, tick: "WAIT"))
    assert result["metrics"]["evacuation_started"] == 0
    assert result["metrics"]["evacuated"] == 0
    assert result["metrics"]["warning_delivered"] == 0
    assert result["metrics"]["exposed"] > 0
    assert not any(e["type"] == "agent_started_evacuating" for e in result["events"])


def test_model_preparation_and_sharing_hold_until_a_later_evacuation_decision():
    warning = GENERIC.model_copy(update={"delivery_reach_probability": 1, "notice_probability": 0,
        "action_probability": 0, "response_delay": 0, "social_share_probability": 0,
        "channels": ["mobile", "social"]})

    def choose(context, tick):
        if tick == 4:
            return "SHARE" if context["id"] % 2 == 0 else "PREPARE"
        return "EVACUATE"

    policy = Policy(choose)
    result = simulate(config(), warning, decision_policy=policy)
    shares = [e for e in result["events"] if e["type"] == "warning_shared"]
    starts = [e for e in result["events"] if e["type"] == "agent_started_evacuating"]
    assert shares and all(e["tick"] == 4 and e["decided_by"] == "bedrock" for e in shares)
    assert starts and all(e["tick"] == 16 for e in starts)
    assert result["frames"][15]["metrics"]["evacuation_started"] == 0
    first = result["frames"][4]["agent_decisions"]
    assert len(first) == 30 and {r["action"] for r in first} == {"PREPARE", "SHARE"}
    assert all(r["tick"] == 4 and r["reason"] for r in first)


def test_resident_context_has_actual_local_perception_routes_neighbors_and_memory():
    policy = Policy(lambda context, tick: "WAIT")
    result = simulate(config(), GENERIC.model_copy(update={"channels": []}), decision_policy=policy)
    assert [c["tick"] for c in policy.calls] == list(MODEL_DECISION_TICKS)
    first = policy.calls[0]
    assert first["warning"]["text"] == GENERIC.text
    for resident in first["residents"]:
        assert resident["goal"] and 0.5 <= resident["trust"] <= 1
        assert resident["warning_received"] is False and resident["perceived_warning"] is None
        if not resident["hazard"]["observed"]:
            assert resident["hazard"]["type"] is None
        assert resident["memory"] == []
        assert len(resident["neighbors"]) >= 1
        assert resident["route"]["available"] is True
        assert resident["route"]["distance_cells"] > 0
        assert resident["available_actions"] == ["WAIT", "PREPARE", "EVACUATE"]
        x, y = resident["position"]
        assert all(abs(px - x) <= 3 and abs(py - y) <= 3
                   for px, py in resident["hazard"]["visible_active_cells"])
    for resident in policy.calls[1]["residents"]:
        assert resident["memory"][0]["tick"] == 4
        assert resident["memory"][0]["action"] == "WAIT"
    assert result["frames"][0]["agent_decisions"] == []


def test_everyday_goals_are_varied_seeded_and_part_of_saved_initial_conditions():
    first = Simulation(config(), GENERIC, decision_policy=Policy())
    repeated = Simulation(config(), GENERIC, decision_policy=Policy())
    changed = Simulation(config(seed=99), GENERIC, decision_policy=Policy())
    goals = [a.goal for a in first.people]
    assert len(set(goals)) >= 4
    assert goals == [a.goal for a in repeated.people]
    assert goals != [a.goal for a in changed.people]
    assert [a["goal"] for a in first.initial_conditions["agents"]] == goals
    assert all("shelter" not in goal.lower() for goal in goals)
    assert all("walking pace is slow" in a.goal for a in first.people if a.movement_speed < 0.7)


def test_unwarned_resident_knows_only_observed_local_hazard():
    model = Simulation(config(), GENERIC.model_copy(update={"channels": []}), decision_policy=Policy())
    resident = model.people[0]
    resident.position = (37, 30)
    model.hazard.step(0)
    unseen = model.resident_context(resident)
    assert unseen["perceived_warning"] is None
    assert unseen["hazard"] == {"type": None, "observed": False, "visible_active_cells": [],
                                "nearest_visible_distance_cells": None}
    resident.position = (21, 3)
    observed = model.resident_context(resident)
    assert observed["hazard"]["observed"] is True
    assert observed["hazard"]["type"] == "flood"
    assert observed["perceived_warning"] is None
    resident.position = (37, 30)
    remembered = model.resident_context(resident)
    assert remembered["hazard"]["observed"] is True
    assert remembered["hazard"]["type"] == "flood"
    assert remembered["hazard"]["visible_active_cells"] == []


@pytest.mark.parametrize("kind", ["flood", "wildfire", "tornado"])
def test_model_cannot_move_residents_through_closed_roads_or_outside_the_graph(kind):
    scenario = config(disaster_type=kind)
    city = make_city(scenario)
    result = simulate(scenario, GENERIC, decision_policy=Policy())
    for before, frame in zip(result["frames"], result["frames"][1:]):
        blocked = {tuple(p) for p in frame["blocked_roads"]}
        graph = nx.subgraph_view(city.graph, filter_node=lambda n, blocked=blocked: n not in blocked)
        assert sum(frame["metrics"]["state_counts"].values()) == scenario.population
        for old, new in zip(before["agents"], frame["agents"], strict=True):
            start, end = tuple(old[1:3]), tuple(new[1:3])
            assert end in city.graph
            if start != end:
                assert start not in blocked and end not in blocked
                assert nx.shortest_path_length(graph, start, end) <= 2
            if STATES[new[3]] == "SHELTERED":
                assert end in city.safe_zones
            if STATES[old[3]] == "SHELTERED":
                assert new == old


def test_incomplete_model_round_fails_before_recording_any_decision():
    policy = Policy()
    policy.decide = lambda residents, warning, scenario, tick: {residents[0]["id"]: Decision("WAIT")}
    model = Simulation(config(), GENERIC, decision_policy=policy)
    with pytest.raises(ValueError, match="exactly one decision"):
        model.run()
    assert not any(e["type"] == "agent_model_decision" for e in model.events)


@pytest.mark.parametrize("action", ["FLY", "SHARE"])
def test_unknown_or_unavailable_model_actions_do_not_fall_back(action):
    model = Simulation(config(), GENERIC.model_copy(update={"channels": []}),
                       decision_policy=Policy(lambda context, tick: action))
    with pytest.raises(ValueError, match="unavailable action"):
        model.run()
    assert not any(e["type"] == "agent_model_decision" for e in model.events)


def test_provider_error_aborts_run_without_replacing_decisions():
    policy = Policy()

    def fail(*args):
        raise RuntimeError("Provider unavailable")

    policy.decide = fail
    with pytest.raises(RuntimeError, match="Provider unavailable"):
        simulate(config(), GENERIC, decision_policy=policy)
