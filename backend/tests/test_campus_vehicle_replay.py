import pytest

from backend.app.simulation.campus_life import CampusLife
from backend.tests.test_campus_calendar_transit import TransitFixture
from backend.tests.test_campus_life import tiny_world


def test_car_impact_stops_speed_and_recovers_with_acceleration_and_same_occupants():
    life = CampusLife(1, 42, city=tiny_world(), transit_enabled=False)
    unit = life.unit_for[0]
    unit.update(stage="driving", override=True, route=[(1., 0.), (2., 0.), (3., 0.)],
                vehicle_id="car-test", current_speed=6.)
    life.vehicles["car-test"] = {"id": "car-test", "position": (0., 0.), "x": 0., "y": 0.,
                                 "occupant_ids": [0], "driver_id": 0, "state": "driving", "speed_mps": 6.}
    life._activity(unit, "travelling by car", "riding")
    life.interrupt(0, 4.)
    assert unit["current_speed"] == life.vehicles["car-test"]["speed_mps"] == 0
    life.step(4, max_step_seconds=1)
    assert life.people[0]["position"] == (0., 0.)
    life.step(1, max_step_seconds=1)
    assert unit["current_speed"] == pytest.approx(1.6)
    assert life.people[0]["position"] == pytest.approx((.16, 0.))
    assert life.vehicles["car-test"]["occupant_ids"] == [0]
    assert life.people[0]["vehicle_id"] == "car-test"


def test_bus_dispatch_and_return_record_visibility_at_physical_event_times():
    life = TransitFixture()
    life._vehicle_visibility = [{"id": key, "at": 0., "visible": False} for key in life.vehicles]
    life.tick()
    assert life._vehicle_visibility[-1] == {"id": "bus-campus-1", "at": 0., "visible": True}
    for _ in range(180):
        life.tick()
    events = [row for row in life._vehicle_visibility if row["id"] == "bus-campus-1"]
    assert [row["visible"] for row in events] == [False, True, False]
    assert 60 < events[-1]["at"] < 180
    assert life.transit.buses[0]["stage"] == "scheduled"
    assert all(not row["visible"] for row in life._vehicle_visibility if row["id"] == "bus-campus-2")


def test_frame_includes_bus_initial_visibility_and_normalized_transition_fractions():
    life = CampusLife(1, 42, city=tiny_world(), transit_enabled=False)
    life.vehicles["bus-test"] = {"id": "bus-test", "type": "bus", "position": (0., 0.),
                                "service_active": False, "state": "scheduled"}
    life._reset_recording()
    life._vehicle_visibility.append({"id": "bus-test", "at": 30., "visible": True})
    life._frame_seconds = 120.
    assert life.frame()["vehicle_visibility_transitions"] == [
        {"id": "bus-test", "fraction": 0., "visible": False},
        {"id": "bus-test", "fraction": .25, "visible": True},
    ]
