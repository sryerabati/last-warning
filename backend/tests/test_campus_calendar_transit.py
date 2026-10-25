from copy import deepcopy
from itertools import pairwise
from types import SimpleNamespace

import networkx as nx
import pytest

from backend.app.simulation.campus_calendar import apply_day_type, service_headway
from backend.app.simulation.campus_transit import CampusTransit, transfer_is_clear, transit_network


def calendar_fixture():
    places = [{"id": "home", "kind": "home", "entrance": [0, 0]},
              {"id": "work", "kind": "school", "entrance": [5, 5]},
              {"id": "shop", "kind": "shop", "entrance": [3, 1]},
              {"id": "park", "kind": "park", "entrance": [3, 3]}]
    roles = ["student", "graduate student", "professor", "staff", "caregiver", "child"]
    profiles = [{"id": i, "role": role, "home_place_id": "home", "work_place_id": "work",
                 "routine": [{"start_minute": 0, "activity": "sleeping", "place_id": "home", "destination": [0, 0], "inside": True},
                             {"start_minute": 540, "activity": "teaching" if role == "professor" else "working" if role == "staff" else "in class", "place_id": "work", "destination": [5, 5], "inside": True}]}
                for i, role in enumerate(roles)]
    return profiles, SimpleNamespace(places=places)


def test_explicit_calendar_preserves_teaching_and_has_distinct_office_breaks():
    profiles, city = calendar_fixture()
    original = deepcopy(profiles)
    apply_day_type(profiles, "teaching", city, 42)
    assert [p["routine"] for p in profiles] == [p["routine"] for p in original]
    apply_day_type(profiles, "class_break", city, 42)
    assert all("in class" not in str(p["routine"]) for p in profiles[:2])
    assert profiles[2]["routine"][1]["activity"] == "research and office work"
    assert profiles[3]["routine"][1]["activity"] == "working"
    assert profiles[4]["routine"] == original[4]["routine"]


@pytest.mark.parametrize("day", ["weekend", "closed"])
def test_non_teaching_days_remove_classes_and_office_commutes_reproducibly(day):
    profiles, city = calendar_fixture()
    other = deepcopy(profiles)
    apply_day_type(profiles, day, city, 42)
    apply_day_type(other, day, city, 42)
    assert profiles == other
    for p in profiles[:4]:
        assert not any(r["place_id"] == "work" for r in p["routine"])
        assert p["routine"][0]["start_minute"] == 0
        assert [r["start_minute"] for r in p["routine"]] == sorted(r["start_minute"] for r in p["routine"])
        if day == "closed":
            assert not any(r["place_id"] == "shop" for r in p["routine"])


def test_service_windows_days_breaks_and_midnight_are_explicit():
    assert service_headway("teaching", 419) is None
    assert service_headway("teaching", 420) == 600
    assert service_headway("teaching", 1080) == 900
    assert service_headway("teaching", 1320) is None
    assert service_headway("weekend", 700) == 1200
    assert service_headway("class_break", 700) == 900
    assert service_headway("class_break", 1140) is None
    assert service_headway("closed", 700) is None
    assert service_headway("teaching", 1440+700) == service_headway("teaching", 700)


def test_non_teaching_outings_disperse_over_accessible_nodes_with_real_waypoints():
    profiles, city = calendar_fixture()
    city.graph = nx.Graph()
    nodes = [(float(i), 3.) for i in range(61)]
    city.graph.add_edges_from(pairwise(nodes))
    for place in city.places:
        city.graph.add_edge(tuple(place["entrance"]), nodes[0])
    city.meters_per_unit = 1
    profiles = [{**deepcopy(profiles[0]), "id": i} for i in range(50)]
    apply_day_type(profiles, "weekend", city, 42)
    outings = [[r for r in p["routine"] if not r["inside"]] for p in profiles]
    destinations = [tuple(r["destination"]) for rows in outings for r in rows]
    assert len(set(destinations)) > 15
    for rows in filter(None, outings):
        assert len(rows) == 3 and len({tuple(r["destination"]) for r in rows}) > 1
        assert all(tuple(r["destination"]) in city.graph for r in rows)


class TransitFixture:
    def __init__(self):
        self.city = SimpleNamespace(meters_per_unit=1)
        self.seed = 42
        self.elapsed_seconds = 420*60.0
        self._event_time = self.elapsed_seconds
        self._frame_start = self.elapsed_seconds
        self._changed_routes = set()
        self._vehicle_motions = {}
        self.weather = {"response": "none", "vehicle_factor": 1.}
        self.vehicles = {}
        self.units = []
        self.people = []
        self.unit_for = {}
        self.events = []
        self.traffic = SimpleNamespace(driving_speed=lambda unit, cruise, seconds: min(cruise, unit.get("current_speed", 0)+1.6*seconds))
        self.places = {"destination": {"name": "Destination"}}
        self.network = {"stops": [{"id": f"stop-{i}", "name": f"Stop {i}", "position": (i*100., 2.), "road_position": (i*100., 0.)} for i in range(3)],
                        "legs": [[(0., 0.), (100., 0.)], [(100., 0.), (200., 0.)], [(200., 0.), (0., 0.)]],
                        "leg_seconds": [17, 17, 34]}
        self.transit = CampusTransit(self, network=self.network)
    @property
    def minute(self):
        return self.elapsed_seconds/60 % 1440
    def _path(self, a, b, unit, blocked=None):
        return [tuple(a), tuple(b)] if not blocked else None
    def _record_activity(self, p, at):
        self.events.append((p["id"], at, p["mode"]))
    def _record_vehicle(self, vehicle, at):
        pass
    def _movement(self, unit, speed, style=None, response=None):
        for key in unit["members"]:
            self.people[key]["speed_mps"] = speed
    def walking_speed(self, unit, factor=1.):
        return unit["speed"]*factor
    def walking_pace(self, unit):
        return unit["speed"], "walk", "none"
    def _move(self, unit, seconds, speed, driving, blocked):
        # Bounded geometric movement so boarding/alighting cannot teleport.
        if blocked:
            return False
        remaining = speed*seconds
        while unit["route"] and remaining > 1e-8:
            end = unit["route"][0]
            a = unit["position"]
            d = ((a[0]-end[0])**2+(a[1]-end[1])**2)**.5
            if d < 1e-8:
                unit["route"].pop(0)
                continue
            step = min(d, remaining)
            unit["position"] = tuple(a[i]+(end[i]-a[i])*step/d for i in (0, 1))
            remaining -= step
            if step == d:
                unit["route"].pop(0)
        for i in unit["members"]:
            self.people[i]["position"] = unit["position"]
        if driving:
            self.vehicles[unit["vehicle_id"]].update(position=unit["position"], x=unit["position"][0], y=unit["position"][1])
        self._event_time = self.elapsed_seconds+seconds
        return not unit["route"]
    def _arrive(self, unit):
        unit["stage"] = "activity"
    def waiters(self, count=1, at=0):
        result = []
        for _ in range(count):
            i = len(self.people)
            pos = self.network["stops"][at]["position"]
            person = {"id": i, "position": pos, "activity": "waiting", "mode": "waiting_bus", "vehicle_id": None, "inside": False, "place_id": None}
            self.people.append(person)
            u = {"id": i, "members": [i], "leader": i, "position": pos, "heading": 0, "stage": "waiting_bus", "held": False,
                 "target": {"place_id": "destination", "destination": (100., 5.), "inside": False}, "speed": 1, "no_steps": False,
                 "vehicle_id": None, "route": [], "transit": {"board": at, "alight": 1, "joined_at": self.elapsed_seconds+i*.01,
                 "own_vehicle_id": None, "bus_id": None, "pending_target": None, "last_path": [(100., 2.), (100., 5.)]}}
            self.units.append(u)
            self.unit_for[i] = u
            result.append(u)
        return result
    def tick(self, dt=1):
        for u in self.units:
            self._event_time = self.elapsed_seconds
            self.transit.step_unit(u, dt, None, 1)
        self.transit.step(dt)
        self.elapsed_seconds += dt


def test_wind_hold_freezes_dwell_and_curb_transfers_without_unloading_people_into_danger():
    fixture = TransitFixture()
    unit = fixture.waiters()[0]
    fixture.tick()
    bus = fixture.transit.buses[0]
    assert unit["stage"] == "boarding_bus"
    bus["impact_until"] = fixture.elapsed_seconds+10
    point, timer = tuple(unit["position"]), bus["timer"]
    for _ in range(5):
        fixture.tick()
    assert unit["position"] == point and unit["stage"] == "boarding_bus"
    assert bus["timer"] == timer and bus["stage"] == "dwelling"
    assert fixture.vehicles[bus["vehicle_id"]]["state"] == "yielding"
    assert not fixture.vehicles[bus["vehicle_id"]]["occupant_ids"]


def test_boarding_requires_stop_presence_capacity_and_fifo_with_no_duplicate_passengers():
    f = TransitFixture()
    units = f.waiters(3)
    f.vehicles["bus-campus-1"]["capacity"] = 1
    units[2]["position"] = (50., 2.)  # Never boards remotely.
    f.tick()
    assert units[0]["stage"] == "boarding_bus"
    assert units[1]["stage"] == units[2]["stage"] == "waiting_bus"
    assert f.vehicles["bus-campus-1"]["occupant_ids"] == []
    f.tick(); f.tick()
    assert units[0]["stage"] == "riding_bus"
    assert f.vehicles["bus-campus-1"]["occupant_ids"] == [0]
    assert f.people[0]["position"] == f.vehicles["bus-campus-1"]["position"]
    for _ in range(8):
        f.tick()
    assert f.vehicles["bus-campus-1"]["occupant_ids"] == [0]
    assert f.transit.missed_capacity == 1


def test_passenger_travels_with_bus_alights_physically_and_continues_foot_trip():
    f = TransitFixture(); unit = f.waiters()[0]
    positions = []
    for _ in range(70):
        f.tick()
        positions.append(f.people[0]["position"])
        if unit["stage"] == "riding_bus":
            assert f.people[0]["position"] == f.vehicles["bus-campus-1"]["position"]
    assert f.transit.boarded == f.transit.completed == 1
    assert unit["stage"] == "walking"
    assert f.people[0]["vehicle_id"] is None
    assert all(0 not in v["occupant_ids"] for v in f.vehicles.values())
    assert max(((b[0]-a[0])**2+(b[1]-a[1])**2)**.5 for a,b in pairwise(positions)) <= 6.01
    assert (100., 2.) in positions


def test_service_suspension_keeps_riders_until_next_stop_and_disables_new_boarding():
    f = TransitFixture(); unit = f.waiters()[0]
    for _ in range(25):f.tick()
    assert unit["stage"] == "riding_bus"
    before = f.people[0]["position"]
    f.transit.suspend("Tornado warning")
    assert f.people[0]["position"] == before
    for _ in range(60):f.tick()
    assert unit["stage"] == "walking"
    assert f.transit.buses[0]["stage"] == "suspended"
    assert not f.transit.frame_fields()["transit"]["service_active"]
    f.transit.resume_service()
    assert f.transit.buses[0]["position"] == (100., 0.)
    for _ in range(22):f.tick()
    assert f.transit.buses[0]["stage"] == "driving"


def test_holiday_no_dispatch_and_closed_service_queue_falls_back_to_walk():
    f = TransitFixture(); f.transit.day_type = "closed"; unit = f.waiters()[0]
    f.tick()
    assert all(b["stage"] == "scheduled" for b in f.transit.buses)
    assert unit["stage"] == "walking" and "transit" not in unit


def test_emergency_destination_while_aboard_defers_to_stop_without_teleport():
    f = TransitFixture(); unit = f.waiters()[0]
    for _ in range(25):f.tick()
    pos = unit["position"]
    target = {"place_id": "destination", "destination": (95., 5.), "inside": True}
    assert f.transit.route_to(unit, target)
    assert unit["position"] == pos and unit["stage"] == "riding_bus"
    for _ in range(60):f.tick()
    assert unit["target"] == target and unit["stage"] == "walking"


def test_missing_source_stops_in_tiny_test_world_disable_transit_instead_of_inventing_stops():
    graph=nx.Graph();graph.add_edge((0.,0.),(1.,1.))
    city=SimpleNamespace(graph=graph,vehicle_graph=graph.to_directed(),meters_per_unit=24.25)
    assert not transit_network(city)["legs"]


def test_trip_plan_does_not_promise_a_stop_after_the_base_terminus():
    f = TransitFixture()
    assert f.transit._ride_seconds(2, 1) is None
    assert f.transit._ride_seconds(2, 0) is not None
    assert f.transit._ride_seconds(0, 2) is not None


def test_curb_transfer_rejects_even_thin_building_and_water_intersections():
    polygon = {"geometry": {"type": "Polygon", "coordinates": [[[4.9, -1], [5.1, -1], [5.1, 1], [4.9, 1], [4.9, -1]]]}}
    for layer in ("buildings", "water"):
        city = SimpleNamespace(geometry={layer: [polygon]})
        assert not transfer_is_clear(city, (0, 0), (10, 0))
        assert transfer_is_clear(city, (0, 2), (10, 2))


def test_aboard_shelter_eta_distinguishes_bus_speed_from_final_walk():
    f = TransitFixture(); unit = f.waiters()[0]
    for _ in range(25): f.tick()
    bus = f.transit.buses[0]
    target = {"place_id": "destination", "destination": (100., 12.), "inside": True}
    expected = (100-bus["position"][0])/6+20+12
    assert f.transit.route_seconds_to(unit, target) == pytest.approx(expected)


def test_wait_intention_can_cancel_a_stop_queue_without_orphan_transit_stage():
    f = TransitFixture(); unit = f.waiters()[0]
    assert f.transit.cancel(unit)
    unit["held"] = True
    assert unit["stage"] not in {"walk_to_bus", "waiting_bus"}
    assert not f.transit.step_unit(unit, 1, None, 1)
    assert "transit" not in unit


def test_boarding_can_abort_on_new_emergency_intention_without_stranding_bus():
    f = TransitFixture(); unit = f.waiters()[0]
    f.tick(); f.tick()
    assert unit["stage"] == "boarding_bus"
    before = unit["position"]
    assert f.transit.route_to(unit, {"place_id": "destination", "destination": (5, 5)}, blocked=None) is None
    assert unit["position"] == before and "transit" not in unit
    assert f.people[0]["vehicle_id"] is None
    assert all(0 not in v["occupant_ids"] for v in f.vehicles.values())


@pytest.mark.parametrize("stage", ["walk_to_bus", "waiting_bus"])
def test_cancelled_service_with_blocked_foot_route_waits_in_place(stage):
    f = TransitFixture(); unit = f.waiters()[0]
    unit["stage"] = stage
    before = unit["position"]
    f.transit.suspend("Tornado warning")
    f.transit.step_unit(unit, 1, lambda _: True, 1)
    assert unit["stage"] == "unreachable"
    assert unit["position"] == before
    assert f.people[0]["mode"] == "waiting" and "transit" not in unit
