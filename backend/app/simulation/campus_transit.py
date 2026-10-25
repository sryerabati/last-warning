"""Conserved passengers on a bounded, source-informed campus shuttle circuit.

Actual OSU stop coordinates and CC headways inform this educational service;
its circuit, 40-person capacity and 20-second dwell are authored. It is not the
full official CABS route or a live arrival prediction.
"""
import json
from itertools import pairwise
from pathlib import Path

import networkx as nx

from .campus_calendar import service_headway
from .campus_world import _crosses_building, distance, project
from .world import uniform

DATA = json.loads((Path(__file__).parents[1]/"data"/"campus_transit_stops.json").read_text())
_NETWORK_CACHE = []
TRANSIT_STAGES = {"walk_to_bus", "waiting_bus", "boarding_bus", "riding_bus", "alighting_bus"}


def transfer_is_clear(city, start, end):
    for layer in ("buildings", "water"):
        for feature in getattr(city, "geometry", {}).get(layer, []):
            geometry = feature.get("geometry", {})
            polygons = geometry.get("coordinates", []) if geometry.get("type") == "MultiPolygon" else [geometry.get("coordinates", [])]
            for rings in polygons:
                if rings and _crosses_building(start, end, rings):
                    return False
    return True


def transit_network(city):
    for cached_city, network in _NETWORK_CACHE:
        if cached_city is city:
            return network
    if not city.vehicle_graph or not city.graph:
        return {"stops": [], "legs": [], "leg_seconds": []}
    component = max(nx.strongly_connected_components(city.vehicle_graph), key=len)
    stops = []
    for row in DATA["stops"]:
        point = project(row["lonlat"])
        road = min(component, key=lambda p: distance(p, point))
        candidates = sorted((p for p in city.graph if distance(p, point)*city.meters_per_unit <= 25), key=lambda p: distance(p, point))
        walk = next((p for p in candidates if transfer_is_clear(city, p, road)), None)
        if walk is None:
            continue
        # Do not connect a distant or missing real stop to an arbitrary street.
        if max(distance(road, point), distance(walk, point))*city.meters_per_unit > 25:
            continue
        stops.append({**row, "position": tuple(walk), "road_position": tuple(road)})
    legs = []
    if len(stops) >= 3:
        for a, b in zip(stops, [*stops[1:], stops[0]]):
            legs.append(nx.shortest_path(city.vehicle_graph, a["road_position"], b["road_position"], weight="weight"))
    network = {"stops": stops, "legs": legs,
               "leg_seconds": [sum(distance(a, b) for a, b in pairwise(path))*city.meters_per_unit/6 for path in legs]}
    _NETWORK_CACHE[:] = [(_c, n) for _c, n in _NETWORK_CACHE[-1:]]+[(city, network)]
    return network


class CampusTransit:
    def __init__(self, life, day_type="teaching", network=None):
        self.life, self.day_type = life, day_type
        self.network = network or transit_network(life.city)
        self.stops, self.legs = self.network["stops"], self.network["legs"]
        self.buses = []
        self.next_departure = 420*60.0
        self.suspended_reason = None
        self.boarded = self.completed = self.missed_capacity = 0
        if not self.legs:
            return
        for index in range(2):
            key = f"bus-campus-{index+1}"
            point = tuple(self.stops[0]["road_position"])
            unit = {"id": key, "traffic_id": key, "members": [], "leader": -1, "position": point,
                    "route": [], "heading": 0.0, "edge_start": None, "edge_end": None,
                    "vehicle_id": key, "no_steps": False, "held": False, "override": True,
                    "stage": "scheduled", "target": {}, "stop": 0, "timer": 0, "returning": False,
                    "lane_offset_m": 1.6, "current_speed": 0.0, "impact_until": 0.0}
            self.buses.append(unit)
            life.vehicles[key] = {"id": key, "position": point, "x": point[0], "y": point[1],
                                  "type": "bus", "color": 0, "state": "scheduled", "occupant_ids": [],
                                  "driver_id": None, "capacity": 40, "heading": 0.0,
                                  "route_id": "campus-cc-corridor", "route_name": DATA["name"],
                                  "next_stop_name": self.stops[0]["name"], "service_active": False, "lane_offset_m": 1.6, "speed_mps": 0.0}
            life._vehicle_motions[key] = [(0.0, point)]

    def traffic_units(self):
        return [b for b in self.buses if b["stage"] in {"driving", "dwelling"}]

    def is_aboard(self, unit):
        return unit["stage"] in {"boarding_bus", "riding_bus", "alighting_bus"}

    def _activity(self, unit, activity, mode, vehicle_id=None):
        for key in unit["members"]:
            person = self.life.people[key]
            old = (person["activity"], person["mode"], person["vehicle_id"], person["inside"], person["place_id"])
            person.update(activity=activity, mode=mode, vehicle_id=vehicle_id, inside=False, place_id=None)
            new = (activity, mode, vehicle_id, False, None)
            if old != new:
                self.life._record_activity(person, self.life._event_time-self.life._frame_start)

    def _ride_seconds(self, board, alight):
        if board == alight or 0 < alight < board:
            return None
        seconds, at = 0.0, board
        while at != alight:
            seconds += self.network["leg_seconds"][at]/self.life.weather["vehicle_factor"]+20
            at = (at+1) % len(self.stops)
        return seconds

    def try_trip(self, unit, target, walk_path, blocked=None):
        if not self.buses or self.suspended_reason or unit.get("override"):
            return False
        headway = service_headway(self.day_type, self.life.minute)
        if headway is None or uniform(self.life.seed, "transit-preference", unit["leader"]) > .75:
            return False
        metres = sum(distance(a, b) for a, b in pairwise(walk_path))*self.life.city.meters_per_unit
        if metres < 550:
            return False
        options = []
        for i, board in enumerate(self.stops):
            if distance(unit["position"], board["position"])*self.life.city.meters_per_unit > 250:
                continue
            first = self.life._path(unit["position"], board["position"], unit, blocked=blocked)
            if not first:
                continue
            first_seconds = sum(distance(a, b) for a, b in pairwise(first))*self.life.city.meters_per_unit/self.life.walking_pace(unit)[0]
            for j, alight in enumerate(self.stops):
                ride = self._ride_seconds(i, j)
                if ride is None or distance(target["destination"], alight["position"])*self.life.city.meters_per_unit > 300:
                    continue
                last = self.life._path(alight["position"], target["destination"], unit, blocked=blocked)
                if not last:
                    continue
                last_seconds = sum(distance(a, b) for a, b in pairwise(last))*self.life.city.meters_per_unit/self.life.walking_pace(unit)[0]
                estimate = first_seconds+headway/2+ride+last_seconds+20
                if estimate < metres/self.life.walking_pace(unit)[0]*1.05:
                    options.append((estimate, i, j, first, last))
        if not options:
            return False
        _, i, j, first, last = min(options)
        unit["transit"] = {"board": i, "alight": j, "last_path": last, "joined_at": None,
                           "own_vehicle_id": unit["vehicle_id"], "bus_id": None, "pending_target": None}
        unit.update(stage="walk_to_bus", route=first)
        self._activity(unit, f"walking to {self.stops[i]['name']} bus stop", "walking")
        return True

    def cancel(self, unit):
        if unit["stage"] == "riding_bus":
            return False
        trip = unit.pop("transit", None)
        if trip:
            unit["vehicle_id"] = trip["own_vehicle_id"]
            unit.update(stage="activity", route=[])
            self._activity(unit, "waiting", "waiting")
        return True

    def route_to(self, unit, target, blocked=None):
        if "transit" not in unit:
            return None
        if unit["stage"] != "riding_bus":
            self.cancel(unit)
            return None
        unit["transit"]["pending_target"] = target
        unit["held"] = False
        unit["override"] = True
        return True

    def path_to(self, unit, target, blocked=None):
        trip = unit.get("transit")
        if not trip:
            return None
        if unit["stage"] in {"boarding_bus", "alighting_bus"}:
            return self.life._path(unit["position"], target["destination"], unit, blocked=blocked)
        bus = next((b for b in self.buses if b["vehicle_id"] == trip.get("bus_id")), None)
        if not bus:
            return None
        index = bus["stop"] if bus["stage"] == "dwelling" else (bus["stop"]+1) % len(self.stops)
        stop = self.stops[index]
        foot = self.life._path(stop["position"], target["destination"], unit, blocked=blocked)
        if not foot:
            return None
        route = [tuple(unit["position"]), *bus["route"], stop["road_position"], stop["position"], *foot[1:]]
        if blocked and any(not self.life._clear_segment(a, b, blocked) for a, b in pairwise(route)):
            return None
        return route

    def route_seconds_to(self, unit, target, blocked=None):
        path = self.path_to(unit, target, blocked)
        if not path:
            return None
        if unit["stage"] in {"boarding_bus", "alighting_bus"}:
            return sum(distance(a, b) for a, b in pairwise(path))*self.life.city.meters_per_unit/self.life.walking_pace(unit)[0]
        bus = next(b for b in self.buses if b["vehicle_id"] == unit["transit"]["bus_id"])
        index = bus["stop"] if bus["stage"] == "dwelling" else (bus["stop"]+1) % len(self.stops)
        stop = self.stops[index]
        road = [tuple(bus["position"]), *bus["route"]] if bus["stage"] == "driving" else [bus["position"]]
        foot = [stop["road_position"], stop["position"], *self.life._path(stop["position"], target["destination"], unit, blocked=blocked)[1:]]
        scale = self.life.city.meters_per_unit
        return (sum(distance(a, b) for a, b in pairwise(road))*scale/(6*self.life.weather["vehicle_factor"]) + 20 +
                sum(distance(a, b) for a, b in pairwise(foot))*scale/self.life.walking_pace(unit)[0])

    def _continue_on_foot(self, unit, activity, blocked):
        target = unit["target"]
        path = self.life._path(unit["position"], target["destination"], unit, blocked=blocked)
        unit.update(stage="walking" if path else "unreachable", route=path or [])
        self.life._changed_routes.update(unit["members"])
        self._activity(unit, activity if path else "waiting for an accessible route", "walking" if path else "waiting")
        if not path and distance(unit["position"], target["destination"]) < 1e-6:
            self.life._arrive(unit)

    def step_unit(self, unit, seconds, blocked, speed_factor):
        stage = unit["stage"]
        if stage not in TRANSIT_STAGES:
            return False
        trip = unit["transit"]
        if stage in {"boarding_bus", "alighting_bus"}:
            bus = next((b for b in self.buses if b["vehicle_id"] == trip.get("bus_id")), None)
            if bus and bus.get("impact_until", 0) > self.life.elapsed_seconds:
                self.life._movement(unit, 0., "brace", "wind_impact")
                return True
        if stage == "walk_to_bus":
            if self.suspended_reason or service_headway(self.day_type, self.life.minute) is None:
                self.cancel(unit)
                self._continue_on_foot(unit, "walking after bus service ended", blocked)
            elif self.life._move(unit, seconds, self.life.walking_speed(unit, speed_factor), False, blocked):
                unit["stage"] = "waiting_bus"
                trip["joined_at"] = self.life._event_time
                self._activity(unit, f"waiting at {self.stops[trip['board']]['name']}", "waiting_bus")
        elif stage == "waiting_bus":
            if self.suspended_reason or service_headway(self.day_type, self.life.minute) is None or self.life.elapsed_seconds-(trip["joined_at"] or 0) > 1800:
                self.cancel(unit)
                self._continue_on_foot(unit, "walking after unavailable bus service", blocked)
        elif stage in {"boarding_bus", "alighting_bus"} and self.life._move(unit, seconds, self.life.walking_speed(unit, speed_factor), False, blocked):
            bus = next(b for b in self.buses if b["vehicle_id"] == trip["bus_id"])
            if stage == "boarding_bus":
                bus["members"].extend(unit["members"])
                unit["stage"] = "riding_bus"
                self.boarded += len(unit["members"])
                self._activity(unit, "riding the campus shuttle", "riding", trip["bus_id"])
            else:
                self.completed += len(unit["members"])
                target = trip["pending_target"] or unit["target"]
                unit["vehicle_id"] = trip["own_vehicle_id"]
                unit.pop("transit")
                unit["target"] = target
                self._continue_on_foot(unit, f"walking to {self.life.places[target['place_id']]['name']}", blocked)
            self._sync_vehicle(bus)
        return True

    def _sync_vehicle(self, bus):
        vehicle = self.life.vehicles[bus["vehicle_id"]]
        active = bus["stage"] not in {"scheduled", "suspended"}
        if active != bool(vehicle.get("service_active")) and hasattr(self.life, "_vehicle_visibility"):
            self.life._vehicle_visibility.append({"id": bus["vehicle_id"], "visible": active,
                                                  "at": self.life._event_time-self.life._frame_start})
        vehicle["occupant_ids"] = sorted(set(bus["members"]))
        if len(vehicle["occupant_ids"]) > vehicle["capacity"]:
            raise RuntimeError("Bus capacity exceeded")
        vehicle.update(state="yielding" if bus["stage"] == "driving" and (bus.get("traffic_wait") or bus.get("held")) else bus["stage"], service_active=active)
        if bus["stage"] != "driving":
            bus["current_speed"] = vehicle["speed_mps"] = 0.0
        if bus.get("impact_until", 0) > self.life.elapsed_seconds:
            vehicle.update(state="yielding" if active else vehicle["state"], speed_mps=0., weather_response="wind_impact")
        else:
            vehicle["weather_response"] = self.life.weather["response"] if active else "none"
        self.life._record_vehicle(vehicle, self.life._event_time-self.life._frame_start)

    def _at_stop(self, bus):
        stop, key = self.stops[bus["stop"]], bus["vehicle_id"]
        returning = bus["returning"] or bool(self.suspended_reason) or service_headway(self.day_type, self.life.minute) is None
        for unit in self.life.units:
            trip = unit.get("transit")
            if not trip or trip.get("bus_id") != key or unit["stage"] != "riding_bus":
                continue
            if trip["alight"] == bus["stop"] or trip["pending_target"] or returning:
                bus["members"] = [p for p in bus["members"] if p not in unit["members"]]
                unit.update(stage="alighting_bus", route=[tuple(bus["position"]), stop["position"]])
                self._activity(unit, f"leaving the bus at {stop['name']}", "alighting", key)
        if not returning:
            waiting = sorted((u for u in self.life.units if u["stage"] == "waiting_bus" and u["transit"]["board"] == bus["stop"]),
                             key=lambda u: (u["transit"]["joined_at"], u["leader"]))
            reserved = sum(len(u["members"]) for u in self.life.units if u["stage"] == "boarding_bus" and u["transit"]["bus_id"] == key)
            for unit in waiting:
                if distance(unit["position"], stop["position"])*self.life.city.meters_per_unit > 2:
                    continue
                if len(bus["members"])+reserved+len(unit["members"]) > self.life.vehicles[key]["capacity"]:
                    if unit["transit"].get("missed_bus") != key:
                        self.missed_capacity += len(unit["members"])
                        unit["transit"]["missed_bus"] = key
                    continue
                reserved += len(unit["members"])
                unit["transit"]["bus_id"] = key
                unit.update(stage="boarding_bus", vehicle_id=key, route=[tuple(unit["position"]), tuple(bus["position"])])
                self._activity(unit, "boarding the campus shuttle", "boarding", key)
        self._sync_vehicle(bus)

    def suspend(self, reason="Service suspended"):
        self.suspended_reason = reason

    def resume_service(self):
        self.suspended_reason = None
        for bus in self.buses:
            if bus["stage"] == "suspended":
                bus.update(stage="dwelling", timer=20.0, held=False)
                self._sync_vehicle(bus)

    def step(self, seconds, blocked=None, speed_factor=1.0):
        now = self.life.elapsed_seconds
        headway = service_headway(self.day_type, self.life.minute)
        if headway and not self.suspended_reason and now >= self.next_departure:
            bus = next((b for b in self.buses if b["stage"] == "scheduled"), None)
            if bus:
                bus.update(stage="dwelling", timer=20.0, stop=0, returning=False, held=False)
                self.life._event_time = now
                self._sync_vehicle(bus)
            self.next_departure = now+headway
        for bus in self.buses:
            impact_until = max([bus.get("impact_until", 0), *[self.life.unit_for[i].get("impact_until", 0) for i in bus["members"]]])
            if bus["stage"] in {"driving", "dwelling"} and now < impact_until:
                bus["current_speed"] = 0.0
                vehicle = self.life.vehicles[bus["vehicle_id"]]
                vehicle.update(speed_mps=0., state="yielding", weather_response="wind_impact")
                self.life._record_vehicle(vehicle, now-self.life._frame_start)
                continue
            if bus["stage"] == "driving":
                bus["held"] = False
                bus["current_speed"] = self.life.traffic.driving_speed(bus, 6*speed_factor*self.life.weather["vehicle_factor"], seconds)
                vehicle = self.life.vehicles[bus["vehicle_id"]]
                vehicle.update(speed_mps=bus["current_speed"], weather_response=self.life.weather["response"])
                self.life._event_time = now
                self.life._movement(bus, bus["current_speed"], "still")
                self.life._record_vehicle(vehicle, now-self.life._frame_start)
                if self.life._move(bus, seconds, bus["current_speed"], True, blocked):
                    bus["current_speed"] = 0.0
                    bus["stop"] = (bus["stop"]+1) % len(self.stops)
                    bus.update(stage="dwelling", timer=20.0, returning=bus["stop"] == 0)
                for resident_id in bus["members"]:
                    unit = self.life.unit_for[resident_id]
                    unit.update(position=tuple(bus["position"]), edge_start=bus["edge_start"], edge_end=bus["edge_end"])
            if bus["stage"] == "dwelling":
                self.life._event_time = now+seconds
                self._at_stop(bus)
                bus["timer"] -= seconds
                transfers = any(u["stage"] in {"boarding_bus", "alighting_bus"} and u["transit"]["bus_id"] == bus["vehicle_id"] for u in self.life.units)
                if bus["timer"] <= 0 and not transfers:
                    if self.suspended_reason:
                        bus["stage"] = "suspended"
                    elif bus["returning"]:
                        bus["stage"] = "scheduled"
                    else:
                        bus.update(stage="driving", route=list(self.legs[bus["stop"]]), held=False)
                        self.life.vehicles[bus["vehicle_id"]]["next_stop_name"] = self.stops[(bus["stop"]+1) % len(self.stops)]["name"]
            self._sync_vehicle(bus)

    def frame_fields(self):
        waiting = {i: sum(len(u["members"]) for u in self.life.units if u["stage"] == "waiting_bus" and u["transit"]["board"] == i) for i in range(len(self.stops))}
        return {"bus_stops": [{"id": s["id"], "name": s["name"], "position": list(s["position"]), "waiting_count": waiting[i]} for i, s in enumerate(self.stops)],
                "transit": {"route_name": DATA["name"], "day_type": self.day_type,
                            "service_active": bool(service_headway(self.day_type, self.life.minute)) and not self.suspended_reason,
                            "suspended_reason": self.suspended_reason, "boarded": self.boarded,
                            "completed_trips": self.completed, "waiting": sum(waiting.values()), "missed_capacity": self.missed_capacity,
                            "scope": DATA["service_scope"]}}
