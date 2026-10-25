"""Authored weather mobility stays physical, recorded and intention-preserving."""
import copy
import json
import math

import networkx as nx

from backend.app.schemas import ScenarioConfig, WarningConfig
from backend.app.simulation.campus_engine import CampusSimulation
from backend.app.simulation.campus_hazards import CampusHazard
from backend.app.simulation.campus_life import CampusLife
from backend.app.simulation.campus_traffic import CampusTraffic
from backend.tests.test_campus_traffic import mover, world


def conditions(kind="blizzard", seconds=3600):
    hazard = CampusHazard(None, ScenarioConfig(layout="campus", disaster_type=kind))
    hazard.step(seconds)
    return hazard.mobility_conditions()


def walker():
    life = CampusLife(30, 42, transit_enabled=False)
    unit = next(u for u in life.units if len(u["members"]) == 1 and life.profiles[u["leader"]]["age"] == "adult" and not u["no_steps"])
    target = next(p for p in life.city.places if p["name"] == "Thompson Library")
    person = life.people[unit["leader"]]
    person.update(inside=False, place_id=None, mode="walking")
    assert life.route_to(unit["leader"], target["id"])
    return life, unit


def test_selected_shelter_trip_physically_hurries_but_ordinary_routine_does_not():
    urgent, unit = walker()
    ordinary = copy.deepcopy(urgent)
    ordinary.unit_for[unit["leader"]]["emergency_pace"] = False
    urgent.step(10); ordinary.step(10)
    fast, slow = urgent.people[unit["leader"]], ordinary.people[unit["leader"]]
    assert fast["walked_m"] > slow["walked_m"]*1.4
    assert fast["movement_style"] == "run" and slow["movement_style"] == "walk"
    assert 0 < fast["speed_mps"] <= 2.4
    assert unit["target"]["place_id"] == ordinary.unit_for[unit["leader"]]["target"]["place_id"]


def test_snow_slows_real_foot_motion_and_remains_after_all_clear():
    clear, unit = walker()
    snow = copy.deepcopy(clear)
    clear.step(10)
    snow.step(10, weather=conditions())
    snowy = snow.people[unit["leader"]]
    assert snowy["movement_style"] == "careful"
    assert snowy["weather_response"] == "snow_caution"
    assert 0 < snowy["walked_m"] < clear.people[unit["leader"]]["walked_m"]*.6
    after = conditions(seconds=14400)
    assert after["response"] == "snow_caution"
    assert after["vehicle_factor"] < after["walk_factor"] < 1
    assert after["headway_seconds"] > 1.2 and after["traction"] < 1


def test_family_and_accessibility_caps_never_generate_a_run_gait():
    life = CampusLife(30, 42, transit_enabled=False)
    family = next(u for u in life.units if len(u["members"]) > 1)
    family["emergency_pace"] = True
    pace, style, _ = life.walking_pace(family)
    assert style == "walk" and pace <= 1.55
    assert family["speed"] == min(life.profiles[i]["movement_speed"] for i in family["members"])
    solo = next(u for u in life.units if len(u["members"]) == 1)
    solo["emergency_pace"] = True
    life.profiles[solo["leader"]]["appearance"]["mobility"] = "wheelchair"
    assert life.walking_pace(solo)[1] == "walk"
    life.weather = conditions()
    assert life.walking_pace(family)[1] == "careful"


def test_snow_increases_headway_and_reduces_acceleration_without_changing_crossing_ownership():
    traffic = CampusTraffic(world())
    trailing = mover(1, (-29., 0.), (30., 0.), True)
    leading = mover(2, (-8., 0.), (30., 0.), True)
    traffic.begin([trailing, leading], {}, 0, 1)
    ordinary, _ = traffic.allowance(trailing, trailing['position'], trailing['route'][-1], 6, 6, True)
    traffic.begin([trailing, leading], {}, 0, 1, headway_seconds=3., traction=.5)
    snow, reason = traffic.allowance(trailing, trailing['position'], trailing['route'][-1], 6, 6, True)
    assert snow < ordinary and reason == "waiting in traffic"
    assert traffic.driving_speed(trailing, 6, 1) <= .8


def contact_simulation():
    config = ScenarioConfig(layout="campus", population=30, seed=42, transit_enabled=True,
                            disaster_type="tornado", hazard_origin=(22, 33), tick_seconds=5, duration_ticks=18)
    warning = WarningConfig(name="Offline contact fixture", text="Simulation fixture: wait for information.", channels=[],
                            notice_probability=0, action_probability=0, delivery_reach_probability=0)
    sim = CampusSimulation(config, warning)
    life = sim.life
    unit = next(u for u in life.units if u["vehicle_id"])
    car = life.vehicles[unit["vehicle_id"]]
    start = min(life.city.vehicle_graph, key=lambda p: math.dist(p, (22, 37)))
    parking = max(life.city.parking, key=lambda p: math.dist(p["position"], start))
    route = nx.shortest_path(life.city.vehicle_graph, start, tuple(parking["position"]), weight="weight")
    life._reserve_destination(unit, parking)
    unit.update(position=start, stage="driving", route=route, override=True, held=False, current_speed=0.)
    car.update(position=start, x=start[0], y=start[1], state="driving", occupant_ids=list(unit["members"]), driver_id=unit["leader"], parking_id=None)
    for key in unit["members"]:
        life.people[key].update(position=start, inside=False, place_id=None)
    life._activity(unit, "travelling by car", "riding")
    preview = copy.deepcopy(life)
    preview.step(30, max_step_seconds=1)
    origin = tuple(round(v) for v in preview.vehicles[car["id"]]["position"])
    sim.hazard.origin = tuple(origin)
    sim.config.hazard_origin = tuple(origin)
    sim.hazard.step(0)
    pedestrian = next(p for p in life.people if p["id"] not in unit["members"] and len(life.unit_for[p["id"]]["members"]) == 1)
    point = min(life.city.graph, key=lambda p: math.dist(p, origin))
    pedestrian.update(position=point, inside=False, place_id=None, mode="waiting")
    life.unit_for[pedestrian["id"]].update(position=point, override=True)
    life.hold(pedestrian["id"])
    # An empty service bus is a real vehicle, despite having no sampled resident.
    bus = life.transit.buses[0]
    bus.update(position=tuple(origin), stage="dwelling", timer=1000, members=[])
    life.vehicles[bus["vehicle_id"]].update(position=tuple(origin), x=origin[0], y=origin[1], state="dwelling", service_active=True)
    life._reset_recording()
    return sim, pedestrian["id"], car["id"], bus["vehicle_id"], origin


def test_tornado_records_vehicle_contact_and_recovery_even_for_empty_service_bus():
    sim, person, car, bus, _ = contact_simulation()
    result = sim.run()
    vehicle_events = [v for f in result["frames"] for v in f["vehicle_impacts"]]
    assert {v["id"] for v in vehicle_events} >= {car, bus}
    assert any(v["contact_ended_at"] is not None and v["recover_until"] > v["contact_ended_at"] for v in vehicle_events)
    assert any(row["id"] == person and row["kind"] == "knockdown" for f in result["frames"] for row in f["agent_impacts"])
    stopped = [v for f in result["frames"] for v in f["vehicles"] if v["id"] == car and v.get("weather_response") in {"wind_impact", "recovering"}]
    assert stopped and all(v["state"] == "yielding" and v["speed_mps"] == 0 for v in stopped)
    assert any(row.get("vehicle_id") == car for f in result["frames"] for row in f["agent_impacts"])
    assert all(v["type"] != "bus" or v["driver_id"] is None for f in result["frames"] for v in f["vehicles"])
    assert json.loads(json.dumps(result))["frames"] == result["frames"]


def test_activity_and_vehicle_transitions_retain_baseline_and_ordered_physical_speeds():
    sim, _, _, _, _ = contact_simulation()
    result = sim.run()
    for frame in result["frames"]:
        for field in ("agent_activity_transitions", "vehicle_state_transitions"):
            grouped = {}
            for row in frame[field]:
                assert row["speed_mps"] >= 0
                grouped.setdefault(row["id"], []).append(row)
            for rows in grouped.values():
                assert rows[0]["fraction"] == 0
                assert [r["fraction"] for r in rows] == sorted(r["fraction"] for r in rows)
        assert all(v["speed_mps"] == 0 for v in frame["vehicles"] if v["state"] in {"parked", "boarding", "alighting", "scheduled", "dwelling", "suspended", "waiting"})


def test_car_snow_speed_reduces_recorded_distance_with_seats_and_route_preserved():
    sim, _, key, _, _ = contact_simulation()
    clear, snow = sim.life, copy.deepcopy(sim.life)
    origin = clear.vehicles[key]["position"]
    clear.step(5, max_step_seconds=1)
    snow.step(5, weather=conditions(), max_step_seconds=1)
    normal, cautious = clear.vehicles[key], snow.vehicles[key]
    assert math.dist(origin, cautious["position"]) < math.dist(origin, normal["position"])
    assert cautious["speed_mps"] < normal["speed_mps"]
    assert cautious["weather_response"] == "snow_caution"
    assert cautious["occupant_ids"] == normal["occupant_ids"]


def test_contact_earlier_in_alighting_slice_does_not_resurrect_parked_car_state():
    sim, _, key, _, point = contact_simulation()
    vehicle = sim.life.vehicles[key]
    old = copy.deepcopy(vehicle)
    old.update(position=point)
    vehicle.update(position=point, occupant_ids=[], driver_id=None, state="parked", speed_mps=0.)
    sim.life._vehicle_motions[key] = []
    sim._before_vehicles = {key: old}
    sim._before_vehicle_motion_counts = {key: 0}
    sim.life.elapsed_seconds = 31
    sim._seconds = 31
    sim._vehicle_reactions(30, 31)
    assert sim.vehicle_impact_history
    assert vehicle["state"] == "parked" and not vehicle["occupant_ids"] and vehicle["speed_mps"] == 0
