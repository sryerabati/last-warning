"""Campus emergency contracts, with deterministic local inference doubles only."""
import copy
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.app.bedrock import (
    CAMPUS_DECISION_PROTOCOL,
    BedrockPolicy,
    Decision,
    DecisionValidationError,
    parse_decisions,
)
from backend.app.schemas import ScenarioConfig, WarningConfig
from backend.app.simulation.campus_engine import CampusSimulation
from backend.app.simulation.campus_hazards import CampusHazard, blizzard_criteria, thunderstorm_category
from backend.app.simulation.engine import simulate


def warning(**kwargs):
    return WarningConfig(name="Campus exercise", text="SIMULATION: Seek a suitable nearby building and await the all-clear.",
                         delivery_reach_probability=1, notice_probability=1, action_probability=1,
                         response_delay=0, **kwargs)


def config(kind="flood", **kwargs):
    return ScenarioConfig(layout="campus", population=10, disaster_type=kind, **kwargs)


@pytest.mark.parametrize("kind,seconds", [("blizzard", 120), ("hailstorm", 30), ("thunderstorm", 30), ("public_safety", 10)])
def test_scenario_clock_defaults_and_legacy_isolation(kind, seconds):
    assert config(kind).tick_seconds == seconds
    with pytest.raises(ValidationError, match="require the campus"):
        ScenarioConfig(disaster_type=kind)
    assert ScenarioConfig().tick_seconds == 5


def test_short_blizzard_and_lightning_hold_cannot_be_mislabeled():
    with pytest.raises(ValidationError, match="3 simulated hours"):
        config("blizzard", duration_ticks=12)
    with pytest.raises(ValidationError, match="1 simulated hour"):
        config("thunderstorm", duration_ticks=12)
    assert config("blizzard", duration_ticks=90).duration_ticks * 120 == 10800


def test_expanded_map_origins_and_weather_cover_the_residential_district():
    from backend.app.simulation.campus_world import CAMPUS_SIZE, DEFAULT_ORIGINS

    assert config().hazard_origin == tuple(DEFAULT_ORIGINS["flood"])
    assert config(hazard_origin=(CAMPUS_SIZE-1, CAMPUS_SIZE-1)).hazard_origin[0] == CAMPUS_SIZE-1
    with pytest.raises(ValidationError, match="inside"):
        config(hazard_origin=(CAMPUS_SIZE, 10))
    with pytest.raises(ValidationError, match="40 × 40"):
        ScenarioConfig(hazard_origin=(CAMPUS_SIZE-1, 10))
    city = SimpleNamespace(size=CAMPUS_SIZE, map_bounds=[1, 9, CAMPUS_SIZE-1, CAMPUS_SIZE-9])
    hazard = CampusHazard(city, config("thunderstorm", hazard_origin=(1, 9)))
    hazard.step(120)
    assert hazard.active_cells == hazard.domain_cells
    assert hazard.danger_at((CAMPUS_SIZE-2, CAMPUS_SIZE-10), seconds=120)
    assert all(1 <= x+.5 <= CAMPUS_SIZE-1 and 9 <= y+.5 <= CAMPUS_SIZE-9
               for x, y in hazard.active_cells)


def test_compound_blizzard_definition_inclusive_threshold_and_missing_data():
    assert blizzard_criteria(35, .25, True, 10800)
    assert not blizzard_criteria(34.99, .25, True, 10800)
    assert not blizzard_criteria(35, .251, True, 10800)
    assert not blizzard_criteria(35, .25, False, 10800)
    assert not blizzard_criteria(35, .25, True, 10799)
    assert not blizzard_criteria(None, .25, True, 10800)
    assert not blizzard_criteria(35, float("nan"), True, 10800)
    assert not blizzard_criteria(35, -1, True, 10800)
    assert thunderstorm_category(80, 0) == "destructive"
    assert thunderstorm_category(0, 2.75) == "destructive"
    assert thunderstorm_category(79.99, 2.74) == "considerable"
    assert thunderstorm_category(57.99, .99) == "ordinary"


def test_lightning_hold_resets_and_uses_simulation_seconds():
    hazard = CampusHazard(None, config("thunderstorm"))
    hazard.step(120)
    assert hazard.last_thunder == 120
    hazard.step(239)
    assert hazard.state()["shelter_hold_seconds_remaining"] == 1681
    hazard.step(240)
    assert hazard.state()["shelter_hold_seconds_remaining"] == 1800
    hazard.step(3599)
    assert not hazard.active and not hazard.all_clear
    assert hazard.state()["phase"] == "shelter_hold"
    hazard.step(3600)
    assert hazard.all_clear and hazard.state()["shelter_hold_seconds_remaining"] == 0
    with pytest.raises(ValueError, match="backwards"):
        hazard.step(0)


def test_indoor_protection_depends_on_hazard_and_actual_occupancy():
    places = {"a": {"id": "a", "entrance": [20, 20], "solid_building": True, "kind": "civic"}}
    inside = {"inside": True, "place_id": "a"}
    for kind in ("blizzard", "hailstorm", "thunderstorm", "tornado"):
        h = CampusHazard(None, config(kind, hazard_origin=(20, 20)))
        h.step(120)
        assert h.protected(inside, places)
        assert not h.protected({"inside": False, "place_id": "a"}, places)
        assert not h.protected({"inside": False, "mode": "riding"}, places)
    for kind in ("flood", "wildfire"):
        h = CampusHazard(None, config(kind, hazard_origin=(20, 20)))
        h.step(120)
        assert not h.protected(inside, places)
    places["a"]["storm_shelter"] = False
    assert not CampusHazard(None, config("tornado")).protected(inside, places)


def test_shelter_selection_does_not_treat_private_houses_as_public_refuges():
    sim = CampusSimulation(config("thunderstorm", town_start_minutes=700), warning())
    person = sim.life.people[0]
    private = next(p for p in sim.city.places if p.get("housing_type") == "house"
                   and p["id"] != sim.life.profiles[0]["home_place_id"])
    person.update(position=tuple(private["entrance"]), inside=False, place_id=None)
    sim.life.unit_for[0]["position"] = person["position"]
    sim.hazard.step(120)
    assert sim.hazard.suitable(private)  # Its own family can still shelter at home.
    assert not sim.can_enter(person, private)
    selected = sim.shelter(person)
    assert selected is not None and selected["id"] != private["id"]
    assert sim.can_enter(person, selected)


def test_shelter_prefers_shorter_executable_route_over_closer_entrance(monkeypatch):
    sim = CampusSimulation(config("thunderstorm"), warning())
    person = sim.life.people[0]
    person.update(position=(0, 0), inside=False, place_id=None, mode="walking")
    sim.life.unit_for[0]["position"] = (0, 0)
    places = [
        {"id": "near-detour", "entrance": (1, 0)},
        {"id": "far-short-route", "entrance": (3, 0)},
        {"id": "blocked", "entrance": (2, 0)},
        {"id": "distant", "entrance": (30, 0)},
    ]
    monkeypatch.setattr(sim.city, "places", places)
    monkeypatch.setattr(sim.life, "places", {place["id"]: place for place in places})
    monkeypatch.setattr(sim.hazard, "suitable", lambda place: True)
    monkeypatch.setattr(sim, "can_enter", lambda person, place: True)
    monkeypatch.setattr(sim, "can_admit", lambda members, place_id: True)
    checked = []

    def path_to(resident_id, place_id, blocked):
        checked.append(place_id)
        return {"near-detour": [(0, 0), (0, 8), (1, 8), (1, 0)],
                "far-short-route": [(0, 0), (3, 0)], "blocked": None}[place_id]

    monkeypatch.setattr(sim.life, "path_to", path_to)
    assert sim.shelter(person)["id"] == "far-short-route"
    assert checked == ["near-detour", "blocked", "far-short-route"]
    # The distant lower bound cannot beat a three-unit executable route.
    assert sim.shelter(person)["id"] == "far-short-route"
    assert len(checked) == 3


def test_shelter_route_ties_are_stable_and_full_or_unreachable_places_are_skipped(monkeypatch):
    sim = CampusSimulation(config("thunderstorm"), warning())
    person = sim.life.people[0]
    person.update(position=(0, 0), mode="walking")
    sim.life.unit_for[0]["position"] = (0, 0)
    places = [{"id": key, "entrance": (distance, 0)}
              for key, distance in [("b", 2), ("a", 2), ("full", 1), ("closed", 1)]]
    monkeypatch.setattr(sim.city, "places", places)
    monkeypatch.setattr(sim.life, "places", {place["id"]: place for place in places})
    monkeypatch.setattr(sim.hazard, "suitable", lambda place: True)
    monkeypatch.setattr(sim, "can_enter", lambda person, place: True)
    monkeypatch.setattr(sim, "can_admit", lambda members, place_id: place_id != "full")
    monkeypatch.setattr(sim.life, "path_to", lambda resident_id, place_id, blocked:
                        None if place_id == "closed" else [(0, 0), (2, 0)])
    assert sim.shelter(person)["id"] == "a"


def test_vehicle_shelter_cost_uses_drive_and_walk_time_not_combined_distance(monkeypatch):
    sim = CampusSimulation(config("thunderstorm"), warning())
    person = sim.life.people[0]
    person.update(mode="driving", position=(0, 0))
    unit = sim.life.unit_for[0]
    unit.update(position=(0, 0), vehicle_id="test-car", speed=1)
    sim.life.vehicles["test-car"] = {"position": (0, 0)}
    places = [{"id": key, "entrance": (distance, 0)} for key, distance in [("long-walk", 2), ("short-walk", 3)]]
    monkeypatch.setattr(sim.city, "places", places)
    monkeypatch.setattr(sim.life, "places", {place["id"]: place for place in places})
    monkeypatch.setattr(sim.hazard, "suitable", lambda place: True)
    monkeypatch.setattr(sim, "can_enter", lambda person, place: True)
    monkeypatch.setattr(sim, "can_admit", lambda members, place_id: True)
    unit_metres = sim.city.meters_per_unit

    def parking_options(unit, place, blocked):
        if place["id"] == "long-walk":
            return [(2*unit_metres, {}, [(0, 0)], [(0, 0), (2, 0)])]
        return [((2.9/6+.1)*unit_metres, {}, [(0, 0), (2.9, 0)], [(2.9, 0), (3, 0)])]

    monkeypatch.setattr(sim.life, "_parking_options", parking_options)
    assert sim.shelter(person)["id"] == "short-walk"


def test_public_safety_has_generic_closures_expansion_and_explicit_all_clear():
    h = CampusHazard(None, config("public_safety"))
    h.step(30)
    assert h.blocked(h.origin)
    first = set(h.blocked_cells)
    h.step(300)
    assert h.blocked_cells > first and h.version == 2
    h.step(900)
    assert h.all_clear and not h.blocked_cells and not h.active_cells
    assert h.state()["simulation"] and h.state()["profile_provenance"] == "authored"


@pytest.mark.parametrize("kind", ["flood", "wildfire", "tornado", "blizzard", "hailstorm", "thunderstorm", "public_safety"])
def test_every_campus_hazard_records_conserved_people_vehicles_and_replay(kind):
    result = simulate(config(kind), warning())
    assert len(result["frames"]) == 121
    assert result["recording_version"] == "last-warning-recording/3"
    assert result["metrics"]["population"] == 10
    assert result["agent_policy"]["usage"] is None
    for frame in result["frames"]:
        assert {row[0] for row in frame["agents"]} == set(range(10))
        assert sum(frame["metrics"]["state_counts"].values()) == 10
        size = result["city"]["size"]
        assert all(0 <= row[1] <= size and 0 <= row[2] <= size and row[4] >= 0 for row in frame["agents"])
        occupants = [key for car in frame["vehicles"] for key in car["occupant_ids"]]
        assert len(occupants) == len(set(occupants))
        for car in frame["vehicles"]:
            assert len(car["occupant_ids"]) <= car["capacity"]
    saved = json.loads(json.dumps(result))
    assert saved["frames"] == result["frames"]
    assert saved["initial_conditions_hash"] == result["initial_conditions_hash"]


def test_subframe_occupancy_does_not_count_a_full_tick_after_entry():
    sim = CampusSimulation(config("blizzard"), warning())
    sim.tick = 1
    sim.hazard.step(120)
    frame = sim.life.frame(1, time=120)
    initial = {**frame["agent_activities"][0], "fraction": 0}
    entry = {**initial, "fraction": .25}
    initial.update(inside=False, place_id=None)
    frame["agent_activity_transitions"].extend([initial, entry])
    sim.integrate_exposure(frame, 120)
    assert sim.meta[0]["exposure"] == 30
    assert all(m["exposure"] == 0 for m in sim.meta[1:])


def test_off_map_commuters_are_neither_exposed_nor_counted_as_in_scene_sheltered():
    sim = CampusSimulation(config("blizzard"), warning())
    portal = next(p for p in sim.city.places if p.get("is_portal"))
    person = sim.life.people[0]
    person.update(position=tuple(portal["entrance"]), place_id=portal["id"], inside=True)
    sim.meta[0]["received"] = True
    sim.hazard.step(120)
    sim.tick = 1
    sim.update_states()
    frame = sim.life.frame(1, time=120)
    frame['agent_activity_transitions'] = []
    sim.integrate_exposure(frame, 120)
    assert sim.meta[0]['exposure'] == 0
    assert sim.meta[0]['state'] == 'ALERTED'
    context = sim.context(person, sim.meta[0])
    assert context['town_life']['outside_scene'] is True
    assert context['route']['destination'] is None
    assert 'SEEK_INDOOR_SHELTER' not in context['available_actions']
    person.update(inside=False, place_id=None)
    sim.integrate_exposure(frame, 120)
    assert sim.meta[0]['exposure'] == 120  # Normal contact resumes after arrival in the scene.


def test_independent_frozen_start_and_same_seed_are_reproducible():
    scenario = config(duration_ticks=12, town_start_minutes=723.5)
    first = simulate(scenario, warning())
    other = simulate(scenario, warning(channels=["siren"]))
    assert first["initial_conditions_hash"] == other["initial_conditions_hash"]
    assert first["frames"][0]["agents"] == other["frames"][0]["agents"]
    assert first["frames"][0]["world_clock_minutes"] == 723.5


class LocalPolicy:
    def __init__(self, choice="WAIT"):
        self.usage = {"model_id": "test-double", "calls": 0}
        self.contexts = []
        self.choice = choice

    def decide(self, residents, warning, scenario, tick):
        self.contexts.append(copy.deepcopy(residents))
        return {r["id"]: Decision("STAY_WITH_GROUP" if "STAY_WITH_GROUP" in r["available_actions"] else self.choice,
                                   "Wait for new information") for r in residents}


def test_bedrock_wait_is_not_silently_replaced_by_rule_evacuation():
    policy = LocalPolicy()
    result = simulate(config(duration_ticks=12, town_start_minutes=720, decision_mode="bedrock"), warning(), decision_policy=policy)
    assert result["agent_policy"]["decision_ticks"] == [2, 8]
    assert len([e for e in result["events"] if e["type"] == "agent_model_decision"]) == 20
    assert result["metrics"]["evacuation_started"] == 0
    assert all(len(r["memory"]) == 1 for r in policy.contexts[1])
    # All movement stops at the actual first decision. A dependent stays with
    # the leader and never receives a false promise that WAIT controls the car.
    assert [row[1:3] for row in result["frames"][2]["agents"]] == [row[1:3] for row in result["frames"][-1]["agents"]]
    for r in policy.contexts[0]:
        if not r["coordination"]["controls_shared_motion"]:
            assert "WAIT" not in r["available_actions"]


def test_unreceived_warning_and_future_field_do_not_leak_to_model_context():
    sim = CampusSimulation(config(duration_ticks=12), warning())
    resident = sim.context(sim.life.people[0], sim.meta[0])
    assert resident["perceived_warning"] is None and resident["latest_update"] is None
    assert resident["hazard"]["type"] is None
    assert resident["route"]["destination"] is None
    assert "SEEK_INDOOR_SHELTER" not in resident["available_actions"]


def test_outdoor_siren_is_a_cue_without_private_message_or_indoor_reception(monkeypatch):
    sim = CampusSimulation(config("thunderstorm", town_start_minutes=700), warning(channels=["siren", "social"]))
    # Pin audibility to isolate channel semantics from the authored reach draw.
    monkeypatch.setattr(sim, "draw", lambda *keys: 0)
    for person in sim.life.people:
        person["inside"] = True
    person = sim.life.people[0]
    person.update(inside=False, place_id=None, mode="walking")
    portal = next(place for place in sim.city.places if place.get("is_portal"))
    sim.life.people[1].update(inside=True, place_id=portal["id"])
    sim.broadcast()
    sim.tick = 1
    sim.broadcast()
    assert sim.meta[0]["siren_heard"] and sim.meta[0]["siren_tick"] == 1
    assert all(not meta["siren_heard"] for meta in sim.meta[1:])
    assert all(not meta["received"] and not meta["noticed"] for meta in sim.meta)
    context = sim.context(person, sim.meta[0])
    assert context["perceived_cues"][0]["type"] == "outdoor_siren"
    assert context["perceived_warning"] is None and not context["warning_received"]
    assert sim.warning.text not in json.dumps(context)
    assert context["hazard"]["type"] is None
    assert context["hazard"]["shelter_hold_seconds_remaining"] is None
    assert "SHARE" not in context["available_actions"]
    assert "SEEK_INDOOR_SHELTER" in context["available_actions"]
    assert context["route"]["available"]
    assert len([event for event in sim.events if event["type"] == "siren_heard"]) == 1
    assert not any(event["type"] == "warning_delivered" for event in sim.events)
    assert sim.metrics()["siren_heard"] == 1 and sim.metrics()["warning_delivered"] == 0


def test_later_mobile_message_still_delivers_after_siren_cue(monkeypatch):
    sim = CampusSimulation(config("thunderstorm", town_start_minutes=700),
                           warning(channels=["mobile", "siren", "social"]))
    monkeypatch.setattr(sim, "draw", lambda *keys: .9 if keys[0] == "campus-mobile-delay" else 0)
    person = sim.life.people[0]
    person.update(inside=False, place_id=None, mode="walking")
    sim.broadcast()
    sim.tick = 1
    sim._seconds = 5
    sim.broadcast()
    assert sim.meta[0]["siren_heard"] and not sim.meta[0]["received"]
    assert "SHARE" not in sim.available_actions(person, sim.meta[0])
    sim.tick = 3
    sim._seconds = 15
    sim.broadcast()
    context = sim.context(person, sim.meta[0])
    assert context["warning_received"] and context["perceived_warning"] == sim.warning.text
    assert "SHARE" in context["available_actions"]
    delivered = [event for event in sim.events if event["type"] == "warning_delivered" and event["agent_id"] == 0]
    assert len(delivered) == 1 and delivered[0]["channel"] == "mobile" and delivered[0]["tick"] == 3


def test_rules_can_respond_to_a_siren_cue_without_fabricating_warning_receipt(monkeypatch):
    sim = CampusSimulation(config("thunderstorm", town_start_minutes=700), warning(channels=["siren", "social"]))
    monkeypatch.setattr(sim, "draw", lambda *keys: 0)
    person = sim.life.people[0]
    person.update(inside=False, place_id=None, mode="walking")
    sim.broadcast()
    sim.tick = 1
    sim.broadcast()
    assert not sim.meta[0]["danger_seen"]
    sim.rules()
    assert sim.meta[0]["action"] == "SEEK_INDOOR_SHELTER"
    assert not sim.meta[0]["received"] and not sim.meta[0]["shared"] and not sim.meta[0]["noticed"]
    assert sim.metrics()["warning_delivered"] == sim.metrics()["warning_shared"] == 0


def test_authored_capacity_counts_units_and_reservations():
    sim = CampusSimulation(config(duration_ticks=12), warning())
    sim.places = copy.deepcopy(sim.places)
    target = sim.life.people[0]["place_id"]
    members = sim.life.unit_for[0]["members"]
    occupied = [p for p in sim.life.people if p["inside"] and p["place_id"] == target]
    sim.places[target]["capacity"] = len(occupied)
    assert sim.can_admit(members, target)
    other = next(unit for unit in sim.life.units if all(sim.life.people[i]["place_id"] != target for i in unit["members"]))
    assert not sim.can_admit(other["members"], target)


def test_invalid_model_choices_raise_without_rule_fallback():
    with pytest.raises(ValueError, match="no rule fallback"):
        simulate(config(duration_ticks=12, decision_mode="bedrock"), warning())
    policy = LocalPolicy("EVACUATE")
    with pytest.raises(ValueError, match="unavailable campus action"):
        simulate(config(duration_ticks=12, decision_mode="bedrock"), warning(), decision_policy=policy)


def test_rules_mode_never_calls_or_misattributes_a_supplied_model_policy():
    policy = LocalPolicy()
    result = simulate(config(duration_ticks=12), warning(), decision_policy=policy)
    assert policy.contexts == [] and result["agent_policy"]["usage"] is None
    assert result["agent_policy"]["decision_count"] == 0


def test_public_safety_updates_are_received_memory_and_never_override_model_wait():
    policy = LocalPolicy()
    result = simulate(config("public_safety", town_start_minutes=720, decision_mode="bedrock"),
                      warning(), decision_policy=policy)
    assert 30 in result["agent_policy"]["decision_ticks"]  # 300-second perimeter update
    assert 90 in result["agent_policy"]["decision_ticks"]  # 900-second explicit all-clear
    update_context = policy.contexts[result["agent_policy"]["decision_ticks"].index(30)]
    clear_context = policy.contexts[result["agent_policy"]["decision_ticks"].index(90)]
    assert all("expanded" in r["latest_update"] for r in update_context)
    assert all(r["hazard"]["all_clear"] is True for r in clear_context)
    assert any(e["type"] == "all_clear" and e["simulation"] for e in result["events"])
    assert [row[1:3] for row in result["frames"][89]["agents"]] == [row[1:3] for row in result["frames"][91]["agents"]]


def test_campus_protocol_is_versioned_and_never_accepted_by_legacy_parser(tmp_path):
    resident = {"id": 3, "available_actions": ["SEEK_INDOOR_SHELTER"], "perceived_warning": None}
    document = {"decisions": [{"id": 3, "action": "SEEK_INDOOR_SHELTER", "reason": "Nearby building is accessible"}]}
    with pytest.raises(DecisionValidationError, match="unavailable action"):
        parse_decisions(json.dumps(document), [resident], allow_routine=True)
    assert parse_decisions(json.dumps(document), [resident], allow_campus=True)[3].action == "SEEK_INDOOR_SHELTER"
    calls = []

    def converse(**request):
        calls.append(request)
        return {"output": {"message": {"content": [{"text": json.dumps(document)}]}}, "stopReason": "end_turn",
                "usage": {"inputTokens": 10, "outputTokens": 20}, "ResponseMetadata": {"RequestId": "campus-test"}}

    policy = BedrockPolicy(tmp_path, client=SimpleNamespace(converse=converse))
    policy.decide([resident], {"text": "HIDDEN MESSAGE"}, {"layout": "campus", "town_life": True}, 2)
    assert policy.usage["decision_protocol"] == CAMPUS_DECISION_PROTOCOL
    assert "HIDDEN MESSAGE" not in calls[0]["messages"][0]["content"][0]["text"]
    assert "STAY_WITH_GROUP" in calls[0]["system"][0]["text"]
    with pytest.raises(DecisionValidationError, match="cannot mix"):
        policy.decide([resident], {}, {}, 8)
