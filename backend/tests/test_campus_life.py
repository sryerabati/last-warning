"""Geography, multimodal conservation, and exact emergency handoff invariants."""
import hashlib
import json
from collections import Counter
from copy import deepcopy
from itertools import pairwise

import networkx as nx
import pytest

from backend.app.simulation.campus_life import CampusLife, appearance, campus_day, make_campus_profiles
from backend.app.simulation.campus_world import DATA, CampusCity, distance, make_campus_city


@pytest.fixture(scope="module")
def day():
    return campus_day(30, 42)


def test_geographic_source_is_pinned_and_metric_networks_remain_separate():
    city = make_campus_city()
    manifest = json.loads((DATA / "osu-district-manifest.json").read_text())
    assert hashlib.sha256((DATA / "osu-district.geojson").read_bytes()).hexdigest() == manifest["geojson_sha256"]
    assert nx.is_connected(city.graph)
    assert nx.is_strongly_connected(city.vehicle_graph)
    assert len(city.graph) > 2000
    assert 20 < city.meters_per_unit < 30
    for graph in (city.graph, city.vehicle_graph):
        for a, b, edge in graph.edges(data=True):
            assert edge["weight"] == pytest.approx(distance(a, b)*city.meters_per_unit)
            assert all(0 <= value <= city.size for point in (a, b) for value in point)
    assert not any(edge["kind"] in {"footway", "pedestrian", "steps"} for _, _, edge in city.vehicle_graph.edges(data=True))
    for parking in city.parking:
        assert tuple(parking["position"]) in city.graph
        assert tuple(parking["position"]) in city.vehicle_graph
    places = {p["name"]: p for p in city.places}
    assert places["Thompson Library"]["entrance"][0] < places["The Oval"]["entrance"][0]
    assert places["Mirror Lake Walk"]["entrance"][1] > places["Thompson Library"]["entrance"][1]
    assert places["Ohio Union"]["entrance"][0] > places["Thompson Library"]["entrance"][0]


def test_restricted_motor_access_is_not_routed_and_one_way_edges_are_preserved():
    city = make_campus_city()
    source = json.loads((DATA / "osu-district.geojson").read_text())
    tags = {f["id"]: f["properties"] for f in source["features"]}
    for a, b, edge in city.vehicle_graph.edges(data=True):
        props = tags[edge["source_id"]]
        access = props.get("motorcar", props.get("motor_vehicle", props.get("vehicle", props.get("access", "yes"))))
        assert access not in {"no", "private", "customers", "delivery"}
        if props.get("oneway") in {"yes", "1", "true", "-1"}:
            reverse = city.vehicle_graph.get_edge_data(b, a)
            assert not reverse or reverse["source_id"] != edge["source_id"]


def test_generated_residents_have_varied_stable_appearances_and_households(day):
    life = CampusLife(300, 42)
    looks = [p["appearance"] for p in life.profiles]
    assert len({json.dumps(look, sort_keys=True) for look in looks}) > 290
    for profile in life.profiles:
        assert profile["appearance"] == appearance(42, profile["id"], profile["age"], profile["role"], profile['household_id'] if profile['household_type'] == 'family' else None)
    assert {1, 2, 3} <= {len(h["members"]) for h in life.households}
    for household in life.households:
        if household["type"] == "family":
            assert any(life.profiles[i]["age"] == "child" for i in household["members"])
            assert any(life.profiles[i]["age"] == "adult" for i in household["members"])
            employed, caregiver, child = household["members"]
            assert life.unit_for[caregiver] is life.unit_for[child]
            assert life.unit_for[employed] is not life.unit_for[child]
    assert day is campus_day(30, 42, "blizzard")


def test_daily_recording_conserves_real_vehicle_occupants_and_returns_everyone_home(day):
    modes = Counter()
    first_vehicles = {v["id"] for v in day["frames"][0]["vehicles"]}
    family_moving_apart = False
    for frame in day["frames"]:
        assert {v["id"] for v in frame["vehicles"]} == first_vehicles
        people = {p[0]: p for p in frame["agents"]}
        activities = {a["id"]: a for a in frame["agent_activities"]}
        riding = set()
        for vehicle in frame["vehicles"]:
            occupants = vehicle["occupant_ids"]
            assert len(occupants) <= vehicle["capacity"]
            assert len(set(occupants)) == len(occupants)
            assert not riding.intersection(occupants)
            riding.update(occupants)
            for key in occupants:
                assert activities[key]["vehicle_id"] == vehicle["id"]
                assert activities[key]["mode"] in {"driving", "riding", "alighting"}
                assert people[key][1:3] == list(vehicle["position"])
            if vehicle["type"] == "bus":
                assert vehicle["driver_id"] is None  # Service operator is outside the resident sample.
            else:
                assert vehicle["driver_id"] in occupants if occupants else vehicle["driver_id"] is None
        for activity in activities.values():
            if activity["mode"] in {"driving", "riding", "alighting"}:
                bus_step_off = activity["mode"] == "alighting" and str(activity["vehicle_id"]).startswith("bus-")
                if bus_step_off:
                    assert activity["id"] not in riding
                else:
                    assert activity["id"] in riding
        for transition in frame["agent_activity_transitions"]:
            modes[transition["mode"]] += 1
        for household in day["households"]:
            if household["type"] == "family" and all(activities[i]["mode"] == "walking" for i in household["members"][1:]):
                family_moving_apart |= len({tuple(people[i][1:3]) for i in household["members"][1:]}) > 1
    assert {"boarding", "driving", "alighting", "walking", "indoors"} <= set(modes)
    assert family_moving_apart
    final = day["frames"][-1]["agent_activities"]
    assert all(a["inside"] and a["place_id"] == day["profiles"][a["id"]]["home_place_id"] for a in final)


def test_motion_preserves_frame_endpoints_and_transition_order(day):
    for previous, frame in pairwise(day["frames"]):
        before = {p[0]: p[1:3] for p in previous["agents"]}
        after = {p[0]: p[1:3] for p in frame["agents"]}
        for motion in frame["agent_motion"]:
            assert motion["path"][0] == pytest.approx(before[motion["id"]], abs=1e-6)
            assert motion["path"][-1] == pytest.approx(after[motion["id"]], abs=1e-6)
            assert motion["fractions"][0] == 0
            assert motion["fractions"][-1] == 1
            assert all(a < b for a, b in pairwise(motion["fractions"]))
        times = {}
        for transition in frame["agent_activity_transitions"]:
            assert 0 <= transition["fraction"] <= 1
            assert transition["fraction"] >= times.get(transition["id"], 0)
            times[transition["id"]] = transition["fraction"]
    assert json.loads(json.dumps(day["frames"][360])) == day["frames"][360]


def test_holding_shared_car_preserves_seats_driver_and_family(day):
    life = CampusLife(30, 42)
    family = next(h for h in life.households if h["type"] == "family")
    unit = life.unit_for[family["members"][1]]
    car = life.vehicles[unit["vehicle_id"]]
    parking = max(life.city.parking, key=lambda p: distance(p["position"], car["position"]))
    route = nx.shortest_path(life.city.vehicle_graph, tuple(car["position"]), tuple(parking["position"]), weight="weight")
    # Arrange a genuine shared trip explicitly: a small demonstration population
    # need not choose a needless car journey merely to exercise a test.
    unit.update(position=tuple(car["position"]), stage="boarding", timer=0, car_route=route, override=True)
    life._reserve_destination(unit, parking)
    life._activity(unit, "boarding the car", "boarding")
    life.step(5)
    assert car["state"] == "driving" and len(car["occupant_ids"]) == 2
    old = deepcopy(car)
    life.hold(car["driver_id"], "waiting for a clear route")
    life.step(45)
    assert car["position"] == old["position"]
    assert car["occupant_ids"] == old["occupant_ids"]
    assert car["driver_id"] == old["driver_id"]
    assert all(life.people[i]["vehicle_id"] == car["id"] for i in car["occupant_ids"])
    leader = car["driver_id"]
    destinations = [p for p in life.city.places if p["solid_building"] and life.can_route(leader, p["id"])]
    assert len(destinations) > 1
    assert life.route_to(leader, destinations[0]["id"])
    assert not life.route_to(next(i for i in car["occupant_ids"] if i != leader), destinations[1]["id"])
    assert car["occupant_ids"] == old["occupant_ids"]


@pytest.mark.parametrize("minute", [492, 720, 1180])
def test_warning_handoff_matches_visible_day_state_exactly(day, minute):
    life = CampusLife(30, 42, start_minute=minute)
    snapshot, expected = life.frame(), day["frames"][minute//2]
    for key in ("agents", "agent_activities", "vehicles"):
        assert snapshot[key] == expected[key]
    frozen = deepcopy(snapshot)
    life.step(60)
    assert snapshot == frozen


def tiny_world():
    graph = nx.Graph()
    for i in range(3):
        graph.add_edge((float(i), 0.0), (float(i+1), 0.0), weight=10.0, steps=False, width_m=3)
    places = [{"id": kind, "name": kind, "kind": kind, "building_type": "house",
               "entrance": [0.0, 0.0] if kind == "home" else [3.0, 0.0],
               "position": [0.0, 0.0] if kind == "home" else [3.0, 0.0],
               "solid_building": kind != "park", "capacity": 10}
              for kind in ("home", "school", "work", "civic", "shop", "park")]
    parking = [{"id": "parking", "position": [0.0, 0.0], "capacity": 10}]
    return CampusCity(graph, nx.DiGraph(graph), places, {}, 10.0, [0, 0, 3, 3], "test", parking)


def test_closure_allows_monotonic_egress_but_never_new_entry():
    life = CampusLife(1, 42, city=tiny_world())

    def blocked(point):
        return point[0] < 2.5

    blocked.egress_score = lambda point: max(0, 2.5-point[0])
    assert life.route_to(0, "school", blocked=blocked)
    life.step(60, blocked=blocked)
    assert life.people[0]["position"] == (3.0, 0.0)
    before = deepcopy(life.people)
    assert not life.can_route(0, "home", blocked=blocked)
    assert not life.route_to(0, "home", blocked=blocked)
    assert life.people == before
    life.hold(0, "stay inside")
    life.step(30, blocked=blocked)
    assert life.people[0]["inside"]
    assert life.people[0]["position"] == (3.0, 0.0)


def test_closure_checks_segment_interior_and_no_entry_after_a_detour():
    life = CampusLife(1, 42, city=tiny_world())
    assert not life.can_route(0, "school", blocked=lambda p: 1.4 < p[0] < 1.6)
    # A closed region at the start permits outward travel, but an unblocked
    # shortcut cannot re-enter it from the other side during reverse search.
    graph = life.city.graph
    graph.add_edge((1.0, 0.0), (1.0, 1.0), weight=10.0, steps=False)
    graph.add_edge((1.0, 1.0), (2.0, 0.0), weight=14.142, steps=False)

    def blocked(point):
        return point[0] < 2.5 and point[1] < .5

    blocked.egress_score = lambda p: max(0, min(2.5-p[0], .5-p[1])) if blocked(p) else 0
    path = life.path_to(0, "school", blocked=blocked)
    assert path
    escaped = False
    for a, b in pairwise(path):
        for j in range(11):
            p = (a[0]+(b[0]-a[0])*j/10, a[1]+(b[1]-a[1])*j/10)
            if escaped:
                assert not blocked(p)
            escaped |= not blocked(p)


def test_interior_capacity_admission_waits_outside_without_teleporting():
    life = CampusLife(1, 42, city=tiny_world())
    assert life.route_to(0, "school")
    life.step(60, admit=lambda members, place_id: False)
    assert life.people[0]["position"] == (3.0, 0.0)
    assert not life.people[0]["inside"]
    assert life.people[0]["activity"] == "building at capacity"
    life.step(5, admit=lambda members, place_id: True)
    assert life.people[0]["inside"]
    assert life.people[0]["position"] == (3.0, 0.0)


def test_authored_building_capacity_enforces_admission_across_routine_units():
    life = CampusLife(2, 42, city=tiny_world())
    life.places["school"]["capacity"] = 1
    for key in range(2):
        assert life.route_to(key, "school")
    for _ in range(12):
        life.step(5)
        assert sum(p["inside"] and p["place_id"] == "school" for p in life.people) <= 1
    assert sum(p["activity"] == "building at capacity" for p in life.people) == 1


def test_campus_population_has_bounded_families_and_credible_housing():
    city = make_campus_city()
    for population in (30, 300, 1000):
        profiles, households = make_campus_profiles(population, 42, city)
        assert len({p['name'].casefold() for p in profiles}) == population
        families = [h for h in households if h['type'] == 'family']
        assert len(families) == (1 if population < 120 else 2)
        places = {p['id']: p for p in city.places}
        family_homes = [places[h['home_place_id']] for h in families]
        assert len({p['id'] for p in family_homes}) == len(families)
        assert all(p['building_type'] == 'house' and p.get('family_home_eligible', True) for p in family_homes)
        households_per_home = Counter(h['home_place_id'] for h in households)
        assert all(households_per_home[p['id']] <= 1 for p in city.places if p.get('housing_type') == 'house')
        assert all(3 <= p['age_years'] <= 5 for p in profiles if p['role'] == 'child')
        assert all(places[p['home_place_id']].get('housing_type') not in {'dormitory', 'student_house'} for p in profiles if p['role'] in {'professor', 'staff', 'caregiver'})
        assert sum(p['role'] in {'student', 'graduate student'} for p in profiles) > population*.70
        assert any(p['role'] == 'graduate student' for p in profiles)
        for p in profiles:
            assert all(p['id'] in profiles[friend]['social_connections'] for friend in p['social_connections'])
        if population == 300:
            looks = [p['appearance'] for p in profiles]
            assert sum(a['headwear'] == 0 for a in looks) > 180
            roommates = [h for h in households if h['type'] == 'roommates']
            assert sum(len({profiles[i]['name'].split()[-1] for i in h['members']}) > 1 for h in roommates) > len(roommates)*.8


def test_all_assigned_routine_targets_are_reachable_without_stairs_when_required():
    life = CampusLife(300, 42)
    step_free = nx.subgraph_view(life.city.graph, filter_edge=lambda a, b: not life.city.graph[a][b].get('steps'))
    components = {node: index for index, nodes in enumerate(nx.connected_components(step_free)) for node in nodes}
    for unit in life.units:
        profile = life.profiles[unit['leader']]
        home = tuple(life.places[profile['home_place_id']]['entrance'])
        for stop in profile['routine']:
            target = tuple(stop['destination'])
            assert target in life.city.graph
            if unit['no_steps']:
                assert components[target] == components[home]
        if len(unit['members']) > 1:
            leader_stops = [(s['start_minute'], s['place_id'], s['destination']) for s in profile['routine']]
            for member in unit['members'][1:]:
                assert [(s['start_minute'], s['place_id'], s['destination']) for s in life.profiles[member]['routine']] == leader_stops


def test_outdoor_stops_are_short_and_leisure_walks_have_distinct_waypoints():
    life = CampusLife(300, 42)
    loops = 0
    for profile in life.profiles:
        for stop, following in pairwise(profile['routine']):
            if not stop['inside']:
                assert following['start_minute']-stop['start_minute'] <= 15
                assert 'walk' not in stop['activity']
                if stop['place_id'] == following['place_id'] and not following['inside']:
                    assert stop['destination'] != following['destination']
                    loops += 1
    assert loops > 100


def test_default_population_does_not_camp_in_parks_and_everyone_completes_day():
    life = CampusLife(300, 42)
    observed_modes = Counter()
    meetings = set()
    family_members = {i for h in life.households if h['type'] == 'family' for i in h['members']}
    max_outdoor_waiting = 0
    for minute in range(0, 1440, 10):
        life.step(minute*60-life.elapsed_seconds)
        assert all(u['stage'] != 'unreachable' for u in life.units)
        waiting = sum(not p['inside'] and p['mode'] == 'waiting' for p in life.people)
        max_outdoor_waiting = max(max_outdoor_waiting, waiting)
        if 660 <= minute <= 840:
            assert waiting < 45
        if minute == 600:
            assert all(life.people[p['id']]['activity'] == 'preschool play at home'
                       for p in life.profiles if p['role'] == 'child')
        if minute == 1210:
            assert all(life.people[p['id']]['activity'] == 'bedtime'
                       for p in life.profiles if p['role'] == 'child')
        observed_modes.update(p['mode'] for p in life.people)
        meetings.update(tuple(m['agent_ids']) for m in life._meetings.values())
    assert max_outdoor_waiting < 60
    assert any(not set(pair).issubset(family_members) for pair in meetings)
    assert observed_modes['walking'] > 100
    assert observed_modes['driving'] > 0
    assert all(p['walked_m'] > 0 for p in life.people)
    assert all(p['inside'] and p['place_id'] == life.profiles[p['id']]['home_place_id'] for p in life.people)


def test_car_owner_walks_when_driving_adds_a_long_detour():
    city = tiny_world()
    city.meters_per_unit = 150
    for a, b, edge in city.graph.edges(data=True):
        edge['weight'] = distance(a, b)*city.meters_per_unit
    city.vehicle_graph = nx.DiGraph()
    points = [(0., 0.), (0., 20.), (3., 20.), (3., 0.)]
    for a, b in pairwise(points):
        city.vehicle_graph.add_edge(a, b, weight=distance(a, b)*city.meters_per_unit)
        city.vehicle_graph.add_edge(b, a, weight=distance(a, b)*city.meters_per_unit)
    city.parking = [{'id': 'start', 'position': [0., 0.], 'capacity': 10},
                    {'id': 'end', 'position': [3., 0.], 'capacity': 10}]
    life = CampusLife(1, 42, city=city)
    unit = life.units[0]
    unit['vehicle_id'] = 'test-car'
    life.vehicles['test-car'] = {'id': 'test-car', 'position': (0., 0.), 'occupant_ids': [],
                                 'parking_id': 'start', 'state': 'parked'}
    target = {'place_id': 'school', 'activity': 'in class', 'inside': True, 'destination': [3., 0.]}
    # Direct walking is 450 m. The road detour is 6.45 km. Owning a car
    # must not override the sensible door-to-door journey choice.
    life._begin(unit, target)
    assert unit['stage'] == 'walking'
    assert life.vehicles['test-car']['state'] == 'parked'
    assert not unit.get('destination_parking')


def test_same_park_waypoint_change_causes_real_motion():
    life = CampusLife(1, 42, city=tiny_world())
    life.profiles[0]['routine'] = [
        {'start_minute': 0, 'activity': 'at home', 'place_id': 'home', 'inside': True, 'destination': [0., 0.]},
        {'start_minute': 1, 'activity': 'taking a break', 'place_id': 'park', 'inside': False, 'destination': [1., 0.]},
        {'start_minute': 2, 'activity': 'taking a break', 'place_id': 'park', 'inside': False, 'destination': [3., 0.]},
    ]
    life.step(100)
    assert life.people[0]['position'] == (1., 0.)
    first_walk = life.people[0]['walked_m']
    life.step(80)
    assert life.people[0]['position'] == (3., 0.)
    assert life.people[0]['walked_m'] > first_walk


def test_meals_and_coffee_only_visit_places_with_the_requested_service():
    city = make_campus_city()
    profiles, _ = make_campus_profiles(300, 42, city)
    places = {p['id']: p for p in city.places}
    counted = Counter()
    for profile in profiles:
        for stop in profile['routine']:
            place = places[stop['place_id']]
            if stop.get('service_kind') == 'food_service':
                assert place.get('food_service'), (profile['id'], stop['activity'], place['name'])
                counted['food'] += 1
            elif stop.get('service_kind') == 'coffee_service':
                assert place.get('coffee_service'), (profile['id'], stop['activity'], place['name'])
                counted['coffee'] += 1
            if stop.get('venue_name'):
                venues = place['coffee_venues'] if stop['service_kind'] == 'coffee_service' else place['food_venues']
                assert stop['venue_name'] in venues
                assert stop['activity'].endswith(f" at {stop['venue_name']}")
    assert counted['food'] > 250 and counted['coffee'] > 30


def test_transient_physical_impact_preserves_route_then_recovers_without_teleport():
    life = CampusLife(1, 42, city=tiny_world(), transit_enabled=False)
    assert life.route_to(0, "school")
    life.step(1, max_step_seconds=1)
    original = tuple(life.people[0]["position"])
    initial_distance = life.people[0]["walked_m"]
    life.interrupt(0, 5, "bracing against the wind")
    samples = []
    life.step(8, max_step_seconds=1, after_substep=lambda at, dt: samples.append((at, tuple(life.people[0]["position"]))))
    assert all(position == original for at, position in samples if at <= 5)
    assert samples[-1][1][0] > original[0]
    assert life.unit_for[0]["override"]
    assert life.people[0]["activity"] != "bracing against the wind"
    assert life.people[0]["walked_m"] == pytest.approx(initial_distance*5)


def test_substep_callbacks_and_callable_speed_use_absolute_seconds():
    life = CampusLife(1, 42, city=tiny_world(), transit_enabled=False)
    life.route_to(0, "school")
    life.unit_for[0]["emergency_pace"] = False  # Isolate the speed-factor clock from urgent gait.
    before, after = [], []
    factor = [1.0]
    def update(at, dt):
        before.append((at, dt))
        factor[0] = .5 if at >= 2 else 1
    life.step(4, max_step_seconds=1, before_substep=update,
              after_substep=lambda at, dt: after.append((at, dt)), speed_factor=lambda: factor[0])
    assert before == [(0, 1), (1, 1), (2, 1), (3, 1)]
    assert after == [(1, 1), (2, 1), (3, 1), (4, 1)]
    assert life.people[0]["walked_m"] == pytest.approx(life.profiles[0]["movement_speed"]*3)


def test_bus_impact_preserves_passenger_mode_and_vehicle_identity_on_recovery():
    from backend.app.simulation.campus_transit import CampusTransit

    life = CampusLife(1, 42, city=tiny_world(), transit_enabled=False)
    life.transit = CampusTransit(life, network={"stops": [], "legs": [], "leg_seconds": []})
    unit, person = life.units[0], life.people[0]
    unit.update(stage="riding_bus", vehicle_id=None, transit={"bus_id": "bus-test"}, override=True)
    person.update(mode="riding", vehicle_id="bus-test", activity="riding the campus shuttle", inside=False, place_id=None)
    life.vehicles["bus-test"] = {"occupant_ids": [0], "driver_id": None, "position": person["position"]}
    life.interrupt(0, 4)
    assert person["mode"] == "riding" and person["vehicle_id"] == "bus-test"
    life.elapsed_seconds = 4
    life._step_unit(unit, 1, None, 1)
    assert person["mode"] == "riding" and person["vehicle_id"] == "bus-test"
    assert person["activity"] == "riding the campus shuttle"
    assert life.vehicles["bus-test"]["occupant_ids"] == [0]
    assert life.vehicles["bus-test"]["driver_id"] is None
