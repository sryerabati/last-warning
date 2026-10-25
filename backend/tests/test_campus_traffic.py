"""Geometric conflicts, conserved waiting motion, headways and fair release."""
import math
from types import SimpleNamespace

import networkx as nx
import pytest

from backend.app.simulation.campus_traffic import CampusTraffic, TrafficGeometry


def world():
    walk = nx.Graph()
    walk.add_edge((0., -30.), (0., 30.), kind="footway", weight=60)
    drive = nx.DiGraph()
    drive.add_edge((-30., 0.), (30., 0.), kind="residential", weight=60)
    drive.add_edge((30., 0.), (-30., 0.), kind="residential", weight=60)
    return SimpleNamespace(graph=walk, vehicle_graph=drive, meters_per_unit=1)


def mover(key, start, end, driving=False, speed=1):
    return {"id": key, "position": start, "route": [start, end], "stage": "driving" if driving else "walking",
            "speed": speed, "heading": math.atan2(end[1]-start[1], end[0]-start[0]), "vehicle_id": str(key) if driving else None}


def test_geometry_finds_segment_interior_crossings_without_inventing_parallel_conflicts():
    city = world()
    geometry = TrafficGeometry(city)
    assert geometry.points == [(0., 0.)]
    city.graph = nx.Graph()
    city.graph.add_edge((-20., 2.), (20., 2.), kind="footway")
    assert TrafficGeometry(city).points == []


def test_simultaneous_crossing_arrival_yields_to_pedestrian_and_car_stops_outside():
    traffic = CampusTraffic(world())
    car = mover(1, (-13., 0.), (30., 0.), True)
    walker = mover(2, (0., -6.2), (0., 30.))
    traffic.begin([car, walker], {}, 0, 1)
    assert traffic.leases[0][0] == traffic.key(walker)
    car_distance, reason = traffic.allowance(car, car['position'], car['route'][-1], 12, 6, True)
    assert car_distance == pytest.approx(5.8)
    assert reason == 'yielding at crossing'
    walk_distance, reason = traffic.allowance(walker, walker['position'], walker['route'][-1], 3, 1, False)
    assert walk_distance == 3 and reason is None
    # A large recording interval cannot let the car leap through the crossing.
    assert car['position'][0]+car_distance < -7


def test_occupied_crossing_retains_owner_until_body_clears_and_waiter_then_proceeds():
    traffic = CampusTraffic(world())
    car = mover(1, (-8., 0.), (30., 0.), True)
    walker = mover(2, (0., -9.), (0., 30.))
    traffic.begin([car, walker], {}, 0, 1)
    assert traffic.leases[0][0] == traffic.key(car)
    car['position'] = (6., 0.)
    car['route'] = [(30., 0.)]
    traffic.begin([car, walker], {}, 4, 1)
    assert traffic.leases[0][0] == traffic.key(car), 'rear must clear before another unit enters'
    car['position'] = (20., 0.)
    car['route'] = [(30., 0.)]
    traffic.begin([car, walker], {}, 8, 1)
    assert traffic.leases[0][0] == traffic.key(walker)


def test_oldest_waiting_arrival_is_not_starved_by_new_requests():
    traffic = CampusTraffic(world())
    car = mover(1, (0., 0.), (30., 0.), True)
    old = mover(2, (0., -6.), (0., 30.))
    traffic.begin([car, old], {}, 0, 1)
    car['position'] = (20., 0.)
    car['route'] = [(30., 0.)]
    new = mover(3, (0., -5.3), (0., 30.))
    traffic.begin([car, old, new], {}, 5, 1)
    assert traffic.leases[0][0] == traffic.key(old)


def test_same_lane_headway_keeps_spacing_and_opposing_lane_does_not_block():
    traffic = CampusTraffic(world())
    following = mover(1, (-25., 0.), (30., 0.), True)
    leader = mover(2, (-13., 0.), (30., 0.), True)
    traffic.begin([following, leader], {}, 0, 1)
    distance, reason = traffic.allowance(following, following['position'], following['route'][-1], 6, 6, True)
    assert distance == 0 and reason == 'waiting in traffic'
    leader['route'] = [leader['position'], (-30., 0.)]
    traffic.begin([following, leader], {}, 1, 1)
    distance, reason = traffic.allowance(following, following['position'], following['route'][-1], 6, 6, True)
    assert distance == 6 and reason is None


def test_no_motor_traffic_does_not_make_pedestrians_queue_for_an_empty_road():
    traffic = CampusTraffic(world())
    walker = mover(2, (0., -6.2), (0., 30.))
    traffic.begin([walker], {}, 0, 5)
    assert traffic.allowance(walker, walker['position'], walker['route'][-1], 10, 1, False) == (10, None)
    assert not traffic.leases


def test_bus_curb_transfer_shares_bus_reservation_instead_of_deadlocking_against_it():
    traffic = CampusTraffic(world())
    bus = {**mover('bus-test', (0., 0.), (30., 0.), True), 'stage': 'dwelling',
           'route': [], 'vehicle_id': 'bus-test', 'traffic_id': 'bus-test'}
    passenger = {**mover(5, (0., -8.), (0., 0.)), 'stage': 'boarding_bus',
                 'vehicle_id': 'bus-test', 'transit': {'bus_id': 'bus-test'}}
    car = mover(1, (-20., 0.), (30., 0.), True)
    traffic.begin([car, passenger, bus], {'bus-test': {'type': 'bus'}}, 0, 1)
    assert traffic.leases[0][0] == 'bus-test'
    assert traffic.allowance(passenger, passenger['position'], (0., 0.), 4, 1, False) == (4, None)
    distance, reason = traffic.allowance(car, car['position'], (30., 0.), 30, 6, True)
    assert distance < 13 and reason in {'yielding at crossing', 'waiting in traffic'}


def test_driving_speed_ramps_up_and_brakes_before_a_headway_limit():
    traffic = CampusTraffic(world())
    car = mover(1, (-25., 0.), (30., 0.), True)
    traffic.begin([car], {}, 0, 1)
    assert traffic.driving_speed(car, 6, 1) == pytest.approx(1.6)
    car['current_speed'] = 6
    leader = mover(2, (-7., 0.), (30., 0.), True)
    traffic.begin([car, leader], {}, 1, 1)
    assert 3 <= traffic.driving_speed(car, 6, 1) < 6
