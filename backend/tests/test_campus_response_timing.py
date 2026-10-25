"""Physical response clocks and visible, recorded ground-contact consequences."""
import copy
import json
import math
from types import SimpleNamespace

import pytest

from backend.app.bedrock import CAMPUS_DECISION_PROTOCOL, BedrockPolicy, Decision
from backend.app.schemas import ScenarioConfig, WarningConfig
from backend.app.simulation.campus_engine import CampusSimulation
from backend.app.simulation.campus_hazards import CampusHazard


def scenario(**values):
    return ScenarioConfig(layout="campus", population=10, transit_enabled=False, **values)


def warning(**values):
    return WarningConfig(name="Timing fixture", text="Simulation: seek a suitable building.",
                         delivery_reach_probability=1, notice_probability=1,
                         action_probability=1, **values)


class WaitPolicy:
    def __init__(self):
        self.usage = {"model_id": "local-fixture"}
        self.calls = []

    def decide(self, people, message, config, tick):
        self.calls.append((config["elapsed_seconds"], copy.deepcopy(people)))
        return {p["id"]: Decision("STAY_WITH_GROUP" if "STAY_WITH_GROUP" in p["available_actions"] else "WAIT", "Remain here") for p in people}


def test_delivery_attention_preparation_and_outcomes_are_output_resolution_invariant():
    results = []
    for resolution in (5, 10, 25):
        config = scenario(disaster_type="public_safety", hazard_origin=(1, 1), tick_seconds=resolution,
                          duration_ticks=300//resolution)
        result = CampusSimulation(config, warning(broadcast_seconds=7, preparation_seconds=9)).run()
        evidence = [(e["type"], e["time"], e["agent_id"]) for e in result["events"]
                    if e["type"] in {"warning_sent", "warning_delivered", "warning_noticed", "agent_started_evacuating"}]
        results.append((evidence, result["metrics"], result["frames"][-1]["agents"]))
    assert results[0] == results[1] == results[2]
    events = results[0][0]
    receipt = {i: at for kind, at, i in events if kind == "warning_delivered"}
    notice = {i: at for kind, at, i in events if kind == "warning_noticed"}
    assert all(12 <= at <= 22 for at in receipt.values())
    assert all(5 <= notice[i]-at <= 20 for i, at in receipt.items())


def test_bedrock_checkpoints_use_physical_seconds_and_keep_round_budget_bounded():
    for resolution in (5, 10, 25):
        policy = WaitPolicy()
        result = CampusSimulation(scenario(decision_mode="bedrock", disaster_type="public_safety",
                                           hazard_origin=(1, 1), tick_seconds=resolution, duration_ticks=600//resolution),
                                  warning(), decision_policy=policy).run()
        # Five standard opportunities plus one explicit authority update at300.
        assert [at for at, _ in policy.calls] == [10, 40, 120, 280, 300, 480]
        assert result["agent_policy"]["decision_times_seconds"] == [at for at, _ in policy.calls]
        assert len(policy.calls) == 6
        assert all(context["elapsed_seconds"] == at for at, contexts in policy.calls for context in contexts)
        assert all("time_seconds" in row for f in result["frames"] for row in f["agent_decisions"])


def test_legacy_warning_fields_use_fixed_reference_seconds_for_new_campus_runs():
    sim = CampusSimulation(scenario(disaster_type="blizzard"), warning(broadcast_tick=3, response_delay=4))
    assert sim.broadcast_at == 15 and sim.preparation_seconds == 20
    explicit = CampusSimulation(scenario(disaster_type="blizzard"),
                                warning(broadcast_tick=3, response_delay=4, broadcast_seconds=7, preparation_seconds=9))
    assert explicit.broadcast_at == 7 and explicit.preparation_seconds == 9


def test_tornado_swept_contact_detects_pass_with_safe_endpoints_and_exact_duration():
    hazard = CampusHazard(None, scenario(disaster_type="tornado", hazard_origin=(10, 20)))
    point = (19, 14.6)  # Center at90s, well outside atboth ends.
    assert not hazard.danger_at(point, 30) and not hazard.danger_at(point, 180)
    contacts = hazard.contact_intervals(point, point, 0, 300)
    half = 1.8/math.hypot(.15, .09)
    assert len(contacts) == 1
    assert contacts[0] == pytest.approx((90-half, 90+half))
    assert sum(b-a for a, b in contacts) == pytest.approx(2*half)
    moving = hazard.contact_intervals((19, 10), (19, 20), 30, 180)
    assert moving and moving[0][0] > 30 and moving[0][1] < 180


def test_public_safety_expansion_is_a_discontinuity_not_early_radius_growth():
    hazard = CampusHazard(None, scenario(disaster_type="public_safety", hazard_origin=(10, 20)))
    assert hazard.contact_intervals((13.9, 20), (13.9, 20), 299, 301) == [(300, 301)]


def test_tornado_impact_records_complete_episode_inside_a_coarse_frame_and_preserves_intent():
    policy = WaitPolicy()
    sim = CampusSimulation(scenario(disaster_type="tornado", hazard_origin=(10, 20),
                                    tick_seconds=120, duration_ticks=12, decision_mode="bedrock"),
                           warning(channels=[]), decision_policy=policy)
    person = sim.life.people[0]
    person.update(position=(10., 20.), inside=False, place_id=None, mode="waiting")
    unit = sim.life.unit_for[0]
    unit["position"] = person["position"]
    sim.life.hold(0)
    result = sim.run()
    impact = next(row for row in result["frames"][1]["agent_impacts"] if row["id"] == 0)
    assert impact["kind"] == "knockdown" and impact["started_at"] == 30
    assert impact["contact_ended_at"] == pytest.approx(30+1.8/math.hypot(.15, .09), abs=1e-6)
    assert impact["recover_until"] == pytest.approx(impact["contact_ended_at"]+8, abs=1e-6)
    assert result["frames"][1]["agents"][0][4] > 10
    assert result["metrics"]["affected_people"] >= 1 and result["metrics"]["hazard_contacts"] >= 1
    assert unit["held"]  # Recovery cannot undo the model's actual WAIT intention.
    assert not unit.get("impact_until")
    assert not result["frames"][-1]["agent_impacts"]
    assert json.loads(json.dumps(result))["frames"] == result["frames"]
    assert not any("injury" in key or "dead" in key for key in result["metrics"])


def test_hazard_motion_records_exact_ground_track_and_active_subframe():
    hazard = CampusHazard(None, scenario(disaster_type="tornado", hazard_origin=(10, 20)))
    motion = hazard.motion(0, 300)
    assert motion["fractions"] == [0, .1, .6, 1]
    assert motion["path"] == [[10, 20], [10, 20], [32.5, 6.5], [32.5, 6.5]]
    assert motion["active_from"] == .1 and motion["active_until"] == .6
    assert hazard.motion(200, 300)["active_from"] is None
    hazard.step(300)
    assert hazard.debris_cells and not hazard.active_cells
    assert hazard.state()["ground_center"] == hazard.state()["center"]
    assert hazard.state()["ground_radius"] == 1.8


def test_initial_active_field_records_contact_without_elapsed_exposure():
    def stop_after_initial_frame():
        raise InterruptedError("Initial frame captured")

    sim = CampusSimulation(scenario(disaster_type="blizzard"), warning(), cancel_check=stop_after_initial_frame)
    person = sim.life.people[0]
    person.update(position=(10., 20.), inside=False, place_id=None, mode="waiting")
    sim.life.unit_for[0]["position"] = person["position"]
    sim.life.hold(0)
    with pytest.raises(InterruptedError, match="Initial frame captured"):
        sim.run()
    impact = next(row for row in sim.frames[0]["agent_impacts"] if row["id"] == 0)
    assert impact["started_at"] == 0 and impact["kind"] == "brace"
    assert impact["contact_ended_at"] is None
    assert sim.frames[0]["agents"][0][4] == 0
    contact = next(row for row in sim.events if row["type"] == "hazard_contact_started" and row["agent_id"] == 0)
    assert contact["time"] == contact["tick"] == 0


def test_bedrock_payload_identifies_exact_second_not_frame_clock(tmp_path):
    requests = []

    def converse(**request):
        requests.append(request)
        return {"output": {"message": {"content": [{"text": '{"decisions":[{"id":0,"action":"WAIT","reason":"Wait here"}]}'}]}},
                "stopReason": "end_turn", "usage": {"inputTokens": 2, "outputTokens": 2},
                "ResponseMetadata": {"RequestId": "timing-local"}}

    policy = BedrockPolicy(tmp_path, client=SimpleNamespace(converse=converse))
    policy.decide([{"id": 0, "available_actions": ["WAIT"]}], {"channels": [], "broadcast_tick": 3},
                  {"layout": "campus", "tick_seconds": 120, "elapsed_seconds": 10}, 1)
    payload = json.loads(requests[0]["messages"][0]["content"][0]["text"])
    assert payload["elapsed_seconds"] == 10 and payload["tick"] == 1
    assert payload["warning_delivery"]["broadcast_seconds"] == 15
    assert "broadcast_tick" not in payload["warning_delivery"]
    assert policy.usage["decision_protocol"] == CAMPUS_DECISION_PROTOCOL


def test_recorded_person_timing_is_truthful_and_warning_independent():
    first = CampusSimulation(scenario(), warning(preparation_seconds=9))
    second = CampusSimulation(scenario(), warning(preparation_seconds=25))
    assert first.initial_hash == second.initial_hash
    for profile in first.initial_conditions["agents"]:
        timing = profile["response_timing_seconds"]
        key = profile["id"]
        assert timing["mobile"] == 5+int(11*first.draw("campus-mobile-delay", key))
        assert timing["attention"] == 5+int(16*first.draw("campus-attention-delay", key))
        assert timing["observation"] == 2+int(6*first.draw("campus-observation-delay", key))
        assert timing["siren"] == timing["social"] == 5
        assert "preparation" not in timing  # This belongs to the warning, not personal initial conditions.
