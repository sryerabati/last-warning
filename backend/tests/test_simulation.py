import copy

import networkx as nx
import pytest

from backend.app.schemas import ACTIONABLE, GENERIC, ScenarioConfig
from backend.app.simulation import Simulation, simulate
from backend.app.simulation.engine import STATES
from backend.app.simulation.world import SAFE_ZONES, make_city


@pytest.fixture(scope="module")
def pair():
    config = ScenarioConfig()
    return simulate(config, GENERIC), simulate(config, ACTIONABLE)


def test_determinism(pair):
    assert simulate(ScenarioConfig(), GENERIC) == pair[0]


def test_common_initial_conditions_and_hazard(pair):
    a, b = pair
    assert a["initial_conditions"] == b["initial_conditions"]
    assert a["initial_conditions_hash"] == b["initial_conditions_hash"]
    assert a["city"] == b["city"]
    assert all(x["hazard_cells"] == y["hazard_cells"] for x, y in zip(a["frames"], b["frames"], strict=True))


def test_text_alone_does_not_change_behavior(pair):
    w = GENERIC.model_copy(update={"text": "Completely different language with identical assumptions."})
    result = simulate(ScenarioConfig(), w)
    assert result["frames"] == pair[0]["frames"]
    assert result["events"] == pair[0]["events"]


def test_assumptions_change_computed_outcomes(pair):
    assert pair[0]["frames"] != pair[1]["frames"]
    assert pair[0]["metrics"]["evacuated"] != pair[1]["metrics"]["evacuated"]


def test_names_do_not_predetermine_results():
    config = ScenarioConfig(population=40, duration_ticks=50)
    w = ACTIONABLE.model_copy(update={"name": "Generic advisory", "text": GENERIC.text})
    assert simulate(config, w)["frames"] == simulate(config, ACTIONABLE)["frames"]


def test_movement_population_and_safety(pair):
    city = make_city(ScenarioConfig())
    for run in pair:
        for previous, frame in zip(run["frames"], run["frames"][1:]):
            blocked = {tuple(p) for p in frame["blocked_roads"]}
            safe_graph = nx.subgraph_view(city.graph, filter_node=lambda n, closed=blocked: n not in closed)
            assert len(frame["agents"]) == 300
            assert len({a[0] for a in frame["agents"]}) == 300
            assert sum(frame["metrics"]["state_counts"].values()) == 300
            for old, new in zip(previous["agents"], frame["agents"], strict=True):
                start, end = tuple(old[1:3]), tuple(new[1:3])
                assert end in city.graph
                if start != end:
                    assert start not in blocked and end not in blocked
                    assert nx.shortest_path_length(safe_graph, start, end) <= 2
                if STATES[new[3]] == "SHELTERED":
                    assert end in SAFE_ZONES
                if STATES[old[3]] == "SHELTERED":
                    assert new == old


def test_legal_transitions(pair):
    allowed = {
        "UNAWARE": {"ALERTED", "PREPARING", "EXPOSED"},
        "ALERTED": {"DECIDING", "PREPARING", "EXPOSED"},
        "DECIDING": {"PREPARING", "EXPOSED"},
        "PREPARING": {"EVACUATING", "EXPOSED"},
        "EVACUATING": {"STRANDED", "SHELTERED", "EXPOSED"},
        "STRANDED": {"EVACUATING", "EXPOSED"},
        "SHELTERED": set(), "EXPOSED": set(),
    }
    for run in pair:
        for event in run["events"]:
            if event["type"] == "state_changed":
                assert event["state"] in allowed[event["previous"]]


def test_flood_closes_roads_and_routes_update(pair):
    for run in pair:
        wet, blocked = set(), set()
        for frame in run["frames"]:
            current = {tuple(x) for x in frame["hazard_cells"]}
            closures = {tuple(x) for x in frame["blocked_roads"]}
            assert current >= wet and closures >= blocked
            assert closures <= current
            assert not closures.intersection(SAFE_ZONES)
            wet, blocked = current, closures
        assert len(wet) > 100 and len(blocked) > 50
        assert run["metrics"]["route_replans"] > 0
        assert run["metrics"]["exposed"] > 0
        assert run["metrics"]["stranded"] > 0


def test_communication_event_order_and_delays(pair):
    for run in pair:
        delivered, noticed, shared = {}, {}, {}
        for e in run["events"]:
            i, t = e["agent_id"], e["tick"]
            if e["type"] == "warning_delivered":
                assert i not in delivered
                delivered[i] = t
                if e["channel"] == "social":
                    assert t >= shared[e["source_agent_id"]] + 2
            elif e["type"] == "warning_noticed":
                assert t > delivered[i]
                noticed[i] = t
            elif e["type"] == "warning_shared":
                assert t >= noticed[i] + 2
                shared[i] = t
        assert len(delivered) == run["metrics"]["warning_delivered"]
        assert len(noticed) == run["metrics"]["warning_noticed"]
        assert len(delivered) > len(noticed)


def test_delivery_and_notice_are_independent():
    w = GENERIC.model_copy(update={"delivery_reach_probability": 1, "notice_probability": 0,
                                  "channels": ["mobile"], "broadcast_tick": 4})
    run = simulate(ScenarioConfig(population=30, duration_ticks=12), w)
    assert run["metrics"]["warning_delivered"] == 30
    assert run["metrics"]["warning_noticed"] == 0
    assert all(e["tick"] >= 5 for e in run["events"] if e["type"] == "warning_delivered")


def test_empty_channels_and_missing_averages():
    run = simulate(ScenarioConfig(population=20, duration_ticks=12), GENERIC.model_copy(update={"channels": []}))
    assert run["metrics"]["warning_delivered"] == 0
    assert run["metrics"]["average_alert_receipt_time"] is None
    assert run["metrics"]["average_decision_delay"] is None


def test_seed_changes_population():
    a = Simulation(ScenarioConfig(population=20, seed=1), GENERIC)
    b = Simulation(ScenarioConfig(population=20, seed=2), GENERIC)
    assert a.initial_hash != b.initial_hash


def test_scrubbing_cannot_mutate_recordings(pair):
    frames = pair[0]["frames"]
    before = copy.deepcopy(frames)
    for i in [0, 20, 100, 3, 120, 0]:
        assert frames[i]["tick"] == i
    assert frames == before


@pytest.mark.parametrize("origin", [(40, 0), (-1, 0), (3, 3), (37, 37)])
def test_invalid_flood_origin(origin):
    with pytest.raises(ValueError):
        ScenarioConfig(hazard_origin=origin)
