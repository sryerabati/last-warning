"""Synthetic campus households, agendas, and conserved multimodal trip state.

The schedules, speeds, capacities and group formations are authored educational
assumptions. Geographic lengths come from the pinned OSM world. No cloud calls.
"""
import math
import threading
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from itertools import pairwise

import networkx as nx

from .campus_identity import biography, family_identity, resident_identity
from .campus_routes import segment_is_clear
from .campus_traffic import CampusTraffic
from .campus_world import distance, make_campus_city
from .life import zero_metrics
from .world import uniform

DAY_VERSION = "osu-campus-life/3.1"
MINUTES_PER_TICK = 2
DAY_TICKS = 720
STATES = ["UNAWARE", "ALERTED", "DECIDING", "PREPARING", "EVACUATING", "SHELTERED", "STRANDED", "EXPOSED"]


def _natural_hair(draw):
    # Palette indices 0–5 are natural shades; 6 is gray and 7 is dyed plum.
    # These are art-direction weights, not measured campus statistics.
    for index, weight in enumerate((.28, .26, .20, .12, .08, .06)):
        draw -= weight
        if draw < 0:
            return index
    return 5


def appearance(seed, resident_id, age="adult", role=None, family_id=None):
    limits = {"body": 4, "skin": 8, "hair": 8, "hair_style": 8, "outfit": 6,
              "top": 12, "bottom": 8, "accessory": 7, "headwear": 5}
    recipe = {key: int(uniform(seed, "appearance", resident_id, key)*limit) for key, limit in limits.items()}
    hair_draw = uniform(seed, "appearance", resident_id, "hair-frequency")
    recipe["hair"] = (6 if age == "older" and hair_draw < .72 else
                      7 if age == "older" and hair_draw < .73 else
                      7 if age == "adult" and hair_draw < .025 else
                      6 if age == "adult" and hair_draw < .07 else
                      _natural_hair(uniform(seed, "appearance", resident_id, "natural-hair")))
    if family_id is not None:
        # Authored resemblance follows a separate household design seed, never
        # a surname or a naming-style label. Variation is retained for relatives.
        anchor = 1+int(uniform(seed, "family-look", family_id, "skin")*6)
        variation = int(uniform(seed, "family-look", resident_id, "skin-variation")*3)-1
        recipe["skin"] = max(0, min(7, anchor+variation))
        if recipe["hair"] < 6 and (age == "child" or uniform(seed, "family-look", resident_id, "hair-affinity") < .82):
            recipe["hair"] = _natural_hair(uniform(seed, "family-look", family_id, "hair"))
    if uniform(seed, "appearance", resident_id, "headwear-frequency") < .70:
        recipe["headwear"] = 0
    if role in {"student", "graduate student"} and uniform(seed, "appearance", resident_id, "book-bag") < .65:
        recipe["accessory"] = 1 if uniform(seed, "appearance", resident_id, "bag-style") < .8 else 2
    return {**recipe, "age": age,
            "mobility": "wheelchair" if age != "child" and uniform(seed, "appearance", resident_id, "mobility") < .035 else "walk"}


def _target(profile, minute):
    minute %= 1440
    return next(row for row in reversed(profile["routine"]) if row["start_minute"] <= minute)


def make_campus_profiles(population, seed, city):
    """An authored campus day, with employment separate from family relationships.

    Two local preschool families are a maximum, not a percentage of a student
    crowd. Campus members have individual class/work schedules. Caregiver-child
    pairs travel together; the other adult keeps their own commitments.
    """
    by_kind = {kind: [p for p in city.places if p["kind"] == kind]
               for kind in ("home", "school", "work", "civic", "shop", "park")}
    step_free = nx.subgraph_view(city.graph, filter_edge=lambda a, b: not city.graph[a][b].get("steps"))
    accessible_nodes = max(nx.connected_components(step_free), key=len)
    # Every assigned home is connected to the main step-free network. This is
    # route feasibility, not a claim of verified real-world accessible entrances.
    homes = [p for p in by_kind["home"] if tuple(p["entrance"]) in accessible_nodes]
    if not homes:
        raise ValueError("Campus needs connected step-free home entrances")
    used_homes, home_residents = Counter(), Counter()
    profiles, households, used_names = [], [], set()
    gathering_nodes = {
        p["id"]: [node for node in city.graph if node in accessible_nodes and
                  distance(node, p["entrance"])*city.meters_per_unit <
                  (110 if p["name"] == "The Oval" else 70)]
        for p in by_kind["park"]
    }
    gathering_assignments = {}

    def gathering_point(place, key, visit=0):
        cache_key = (place["id"], key, visit)
        if cache_key not in gathering_assignments:
            nodes = gathering_nodes[place["id"]] or [tuple(place["entrance"])]
            previous = gathering_assignments.get((place["id"], key, visit-1))
            if previous:
                nearby = [node for node in nodes if 18 < distance(node, previous)*city.meters_per_unit < 65]
                nodes = nearby or nodes
            # Distinct households use distinct rendezvous nodes. The same family
            # can meet again, while unrelated schedules do not share a park hub.
            chosen = min(nodes, key=lambda node: uniform(seed, "outdoor-stop", key, visit, node))
            gathering_assignments[cache_key] = chosen
        return gathering_assignments[cache_key]

    def housing_type(place):
        return place.get("housing_type") or {"apartments": "apartment"}.get(place.get("building_type"), place.get("building_type"))

    def choose_home(household_type, role, count, h):
        if household_type == "family":
            preferred = [p for p in homes if housing_type(p) == "house" and not used_homes[p["id"]]]
        elif role == "student":
            category = "dormitory" if uniform(seed, "student-housing", h) < .63 else "apartment"
            preferred = [p for p in homes if housing_type(p) == category]
        elif role == "graduate student":
            preferred = [p for p in homes if housing_type(p) == "apartment"]
        else:
            category = "commuter" if role in {"professor", "staff"} and uniform(seed, "commuter", h) < .45 else "apartment"
            preferred = [p for p in homes if housing_type(p) == category]
        def room(p):
            household_capacity = p.get("household_capacity", 1 if housing_type(p) == "house" else 1000)
            return used_homes[p["id"]] < household_capacity and home_residents[p["id"]]+count <= p.get("capacity", 180)
        available = [p for p in preferred if room(p)]
        if not available:
            available = [p for p in homes if housing_type(p) not in {"house", "dormitory"} and room(p)]
        if not available:
            available = [p for p in homes if housing_type(p) != "house" and room(p)]
        if not available and all(housing_type(p) == "house" for p in homes):
            # Small synthetic test worlds can contain only one dwelling type.
            available = [p for p in homes if room(p)]
        if not available:
            raise ValueError("Campus population exceeds the authored housing capacity")
        # Families must have actual houses, never an apartment/dorm fallback.
        if household_type == "family":
            available = [p for p in available if housing_type(p) == "house"]
            if not available:
                raise ValueError("Local family needs an unoccupied connected house")
        return min(available, key=lambda p: (home_residents[p["id"]]/max(1, p.get("capacity", 180)),
                                             uniform(seed, "home", h, p["id"])))

    available_houses = sum(housing_type(p) == "house" for p in homes)
    family_count = min(2 if population >= 120 else 1 if population >= 12 else 0, available_houses)
    # A campus-focused demonstration mix, not a demographic estimate of OSU.
    mix = [("student", 3), ("student", 2), ("graduate student", 2), ("student", 3),
           ("staff", 1), ("student", 2), ("professor", 1), ("graduate student", 1),
           ("student", 3), ("neighbor", 1)]
    while len(profiles) < population:
        h = len(households)
        family = h < family_count
        role, desired_count = ("professor" if h % 2 == 0 else "staff", 3) if family else mix[(h-family_count) % len(mix)]
        count = min(desired_count, population-len(profiles))
        household_type = "family" if family else "roommates" if count > 1 else "solo"
        home = choose_home(household_type, role, count, h)
        members = list(range(len(profiles), len(profiles)+count))
        household_id = f"campus-household-{h+1}"
        family_names = family_identity(seed, household_id) if family else None
        for index, key in enumerate(members):
            actual_role = (role if index == 0 else "caregiver" if index == 1 else "child") if family else role
            age = "child" if actual_role == "child" else "older" if actual_role == "neighbor" and h % 3 == 0 else "adult"
            age_years = (3+int(uniform(seed, "age", key)*3) if age == "child" else
                         65+int(uniform(seed, "age", key)*13) if age == "older" else
                         18+int(uniform(seed, "age", key)*6) if actual_role == "student" else
                         23+int(uniform(seed, "age", key)*10) if actual_role == "graduate student" else
                         30+int(uniform(seed, "age", key)*30))
            look = appearance(seed, key, age, actual_role, household_id if family else None)
            no_steps = look["mobility"] == "wheelchair"
            def choose(kind, salt, service=None, person=key, step_free_required=no_steps):
                service_metadata = service and any(service in p for p in city.places)
                pool = [p for p in city.places if p.get(service)] if service_metadata else by_kind[kind]
                candidates = [p for p in pool if not step_free_required or tuple(p["entrance"]) in accessible_nodes]
                if not candidates:
                    raise ValueError(f"Campus needs a reachable {service or kind} destination")
                if kind == "work":
                    useful = [p for p in candidates if not p.get("is_parking") and "Pump House" not in p["name"] and "Maintenance" not in p["name"]]
                    candidates = useful or candidates
                return min(candidates, key=lambda p: uniform(seed, salt, person, p["id"]))
            work = choose("school" if actual_role in {"student", "graduate student", "professor"} else "work", "workplace")
            if actual_role in {"child", "caregiver"}:
                work = home
            display_name, identity = resident_identity(seed, key, used_names, family_names)
            # The caregiver (adult) leads the dependent; the employed adult is
            # independent instead of dragging every family member into work.
            travel_members = members[1:] if family and index > 0 else [key]
            group_id = household_id if family and index > 0 else None
            profile = {"id": key, "name": display_name, "identity": identity,
                       "biography": biography(seed, key, actual_role), "household_id": household_id,
                       "household_type": household_type, "household_members": members,
                       "home_place_id": home["id"], "work_place_id": work["id"], "role": actual_role,
                       "family_relationship": "child" if family and index > 1 else "parent" if family else None,
                       "age": age, "age_years": age_years, "appearance": look, "group_id": group_id,
                       "travel_members": travel_members,
                       "goal": f"Keep my commitments and return to {home['name']}.",
                       "trust": .5+.5*uniform(seed, "trust", key), "reaction_delay": int(6*uniform(seed, "reaction", key)),
                       "movement_speed": (.85 if age in {"child", "older"} else 1.1)+.35*uniform(seed, "pace", key),
                       "speed_units": "metres/second", "social_connections": sorted(set(members)-{key}), "routine": []}
            routine = profile["routine"]
            def at(minute, activity, place, inside=True, destination=None, routine=routine, person=key):
                service = ("coffee_service" if activity == "getting coffee" else
                           "food_service" if activity in {"getting lunch", "snack break"} else None)
                venue = None
                if service:
                    venues = place.get("coffee_venues" if service == "coffee_service" else "food_venues", [])
                    if venues:
                        venue = min(venues, key=lambda name: uniform(seed, "service-venue", person, activity, name))
                routine.append({"start_minute": int(minute), "activity": activity, "place_id": place["id"],
                                "inside": inside, "destination": list(destination or place["entrance"])})
                if service:
                    routine[-1]["service_kind"] = service
                    if venue:
                        routine[-1].update(activity=f"{activity} at {venue}", venue_name=venue)
            def outing(minute, park, duration=15, visit_key=key):
                # Walking actually traverses a short loop; stop labels describe
                # the brief pauses, not a frozen character claiming to walk.
                for visit, label in enumerate(("taking a short break", "enjoying the view", "resting before the next stop")):
                    at(minute+visit*max(4, duration//3), label, park, False, gathering_point(park, visit_key, visit))
            offset = int(uniform(seed, "schedule", key)*70)
            park = choose("park", "park")
            shop, civic = choose("shop", "lunch"), choose("civic", "study")
            food, cafe = choose("shop", "lunch", "food_service"), choose("shop", "coffee", "coffee_service")
            at(0, "sleeping", home)
            at(390+offset, "at home", home)
            if actual_role in {"caregiver", "child"}:
                # Preschool children are locally cared for; no implied school
                # attendance or invented real school/childcare destination.
                outing_key = members[1]
                park = min(by_kind["park"], key=lambda p: uniform(seed, "family-park", h, p["id"]))
                start = 890+int(uniform(seed, "family-outing", h)*90)
                at(510, "preschool play at home" if actual_role == "child" else "caring for preschooler at home", home)
                at(720, "lunch at home", home)
                outing(start, park, 24, outing_key)
                at(start+30, "snack break", food)
                at(start+60, "at home", home)
                at(1200, "bedtime" if actual_role == "child" else "at home", home)
            elif actual_role in {"student", "graduate student"}:
                start = 480+int(uniform(seed, "first-class", key)*170)
                second = choose("school", "second-class")
                at(start, "in class" if actual_role == "student" else "research seminar", work)
                first_end = start+50+int(uniform(seed, "class-length", key)*30)
                if uniform(seed, "short-break", key) < .42:
                    outing(first_end, park)
                    first_end += 18
                at(first_end, "studying between classes", civic)
                lunch = max(first_end+35, 680+int(uniform(seed, "lunch-time", key)*105))
                at(lunch, "getting lunch", food)
                at(lunch+30+int(uniform(seed, "lunch-length", key)*15), "in class" if actual_role == "student" else "research work", second)
                at(lunch+100+int(uniform(seed, "afternoon", key)*45), "studying", civic)
                end = max(lunch+165, 990+int(uniform(seed, "go-home", key)*150))
                if uniform(seed, "evening-study", key) < .18:
                    end = 1170+int(uniform(seed, "late-home", key)*90)
                if uniform(seed, "coffee", key) < .30:
                    at(end-25, "getting coffee", cafe)
                at(end, "at home", home)
            elif actual_role in {"professor", "staff"}:
                start = (460 if actual_role == "professor" else 420)+int(uniform(seed, "work-start", key)*100)
                at(start, "office work" if actual_role == "professor" else "working", work)
                if actual_role == "professor":
                    at(start+60, "teaching", choose("school", "teaching"))
                    at(start+150, "office hours", work)
                lunch = 690+int(uniform(seed, "lunch-time", key)*90)
                at(lunch, "getting lunch", food)
                if uniform(seed, "short-break", key) < .25:
                    outing(lunch+25, park, 12)
                at(lunch+40, "working", work)
                at(990+int(uniform(seed, "go-home", key)*100), "at home", home)
            else:
                start = 560+int(uniform(seed, "errand-time", key)*100)
                at(start, "running an errand", shop)
                at(start+35, "at home", home)
                start = 900+int(uniform(seed, "local-walk", key)*160)
                outing(start, park, 21)
                at(start+28, "at home", home)
            at(1300+int(uniform(seed, "bedtime", key)*80), "sleeping", home)
            # Sort before target selection; neighboring entries never share a
            # time after optional class/break choices are assembled.
            by_time = {row["start_minute"]: row for row in routine}
            profile["routine"] = [by_time[t] for t in sorted(by_time)]
            profiles.append(profile)
        used_homes[home["id"]] += 1
        home_residents[home["id"]] += count
        households.append({"id": household_id, "type": household_type, "members": members,
                           "home_place_id": home["id"]})
    for household in households:
        if household["type"] == "family":
            caregiver = profiles[household["members"][1]]
            for member in household["members"][2:]:
                profiles[member]["routine"] = deepcopy(caregiver["routine"])
                for stop in profiles[member]["routine"]:
                    if stop["activity"] == "caring for preschooler at home":
                        stop["activity"] = "preschool play at home"
                    elif stop["start_minute"] == 1200:
                        stop["activity"] = "bedtime"
        elif household["type"] == "roommates" and uniform(seed, "planned-meeting", household["id"]) < .22:
            members = household["members"]
            minute = 1035+int(uniform(seed, "meeting-time", household["id"])*90)
            park = min(by_kind["park"], key=lambda p: uniform(seed, "meeting-park", household["id"], p["id"]))
            hub = gathering_point(park, household["id"], 0)
            companions = [node for node in gathering_nodes[park["id"]]
                          if 1.5 < distance(node, hub)*city.meters_per_unit < 4.5]
            for index, member in enumerate(members):
                profile = profiles[member]
                point = companions[index % len(companions)] if index and companions else hub
                # A short social appointment replaces only late study/coffee
                # time. It never sends the entire campus to a compulsory party.
                routine = [row for row in profile["routine"] if row["start_minute"] < minute or row["start_minute"] >= 1280]
                routine.extend([
                    {"start_minute": minute, "activity": "catching up with roommates", "place_id": park["id"],
                     "inside": False, "destination": list(point)},
                    {"start_minute": minute+12, "activity": "at home", "place_id": profile["home_place_id"],
                     "inside": True, "destination": list(next(p["entrance"] for p in homes if p["id"] == profile["home_place_id"]))},
                ])
                profile["routine"] = sorted(routine, key=lambda row: row["start_minute"])
    # Social ties are reciprocal and local: household members, classmates and
    # coworkers. A person ID offset is not a meaningful friendship network.
    cohorts = {}
    for p in profiles:
        cohorts.setdefault((p["work_place_id"], p["role"]), []).append(p["id"])
    for peers in cohorts.values():
        if len(peers) > 1:
            for index, person_id in enumerate(peers):
                for friend in (peers[(index+1) % len(peers)], peers[(index-1) % len(peers)]):
                    profiles[person_id]["social_connections"].append(friend)
                    profiles[friend]["social_connections"].append(person_id)
    for p in profiles:
        p["social_connections"] = sorted(set(p["social_connections"])-{p["id"]})
    return profiles, households


class CampusLife:
    def __init__(self, population=300, seed=42, start_minute=0, city=None, campus_day_type="teaching", transit_enabled=True):
        self.city = city or make_campus_city()
        self.seed = seed
        self.campus_day_type = campus_day_type
        self.transit_enabled = transit_enabled
        self.profiles, self.households = make_campus_profiles(population, seed, self.city)
        from .campus_calendar import apply_day_type
        apply_day_type(self.profiles, campus_day_type, self.city, seed)
        self.places = {p["id"]: p for p in self.city.places}
        self.people = []
        self.vehicles = {}
        self.units = []
        self.unit_for = {}
        self.elapsed_seconds = 0.0
        self.tick = 0
        self._paths = {}
        self._path_trees = {}
        target_counts = Counter(tuple(row["destination"]) for p in self.profiles for row in p["routine"])
        self._frequent_targets = {point for point, count in target_counts.items() if count > 6}
        self._blocked = None
        self._admit = None
        self._motions = {}
        self._vehicle_motions = {}
        self._vehicle_visibility = []
        self._transitions = []
        self._vehicle_states = []
        self._last_vehicle_states = {}
        self.weather = {"response": "none", "walk_factor": 1., "vehicle_factor": 1., "headway_seconds": 1.2, "traction": 1.}
        self._frame_start = 0.0
        self._frame_seconds = 0.0
        self._event_time = 0.0
        self._meetings = {}
        self._meeting_cooldown = {}
        self._parking_reserved = Counter()
        self._changed_routes = set()
        self.traffic = CampusTraffic(self.city)
        self.transit = None
        for profile in self.profiles:
            home = self.places[profile["home_place_id"]]
            self.people.append({"id": profile["id"], "position": tuple(home["entrance"]),
                                "inside": True, "place_id": home["id"], "destination_place_id": home["id"],
                                "activity": "sleeping", "mode": "indoors", "vehicle_id": None,
                                "group_id": profile["group_id"], "partner_ids": [], "walked_m": 0.0,
                                "movement_style": "still", "speed_mps": 0.0, "weather_response": "none"})
        for household in self.households:
            member_groups = []
            for resident_id in household["members"]:
                group = self.profiles[resident_id].get("travel_members", [resident_id])
                if group not in member_groups:
                    member_groups.append(group)
            for members in member_groups:
                leader = members[0]
                profile = self.profiles[leader]
                unit = {"id": len(self.units), "members": members, "leader": leader,
                        "position": self.people[leader]["position"], "stage": "activity", "route": [],
                        "edge_start": None, "edge_end": None, "target": _target(profile, 0),
                        "heading": 0.0,
                        "override": False, "held": False, "vehicle_id": None, "timer": 0.0,
                        "current_speed": 0.0, "traffic_wait": None, "next_agenda_seconds": 0.0,
                        "speed": min(self.profiles[i]["movement_speed"] for i in members),
                        "no_steps": any(self.profiles[i]["appearance"]["mobility"] == "wheelchair" for i in members)}
                wants_car = profile["role"] == "caregiver" or (profile["role"] in {"professor", "staff", "neighbor"} and uniform(seed, "car-access", leader) < .6)
                available = [p for p in self.city.parking if self._parking_reserved[p["id"]] < p["capacity"]]
                parking = min(available or self.city.parking, key=lambda p: distance(p["position"], unit["position"]))
                if wants_car and self._parking_reserved[parking["id"]] < parking["capacity"]:
                    vehicle_id = f"car-{len(self.vehicles)+1}"
                    unit["vehicle_id"] = vehicle_id
                    point = tuple(parking["position"])
                    self.vehicles[vehicle_id] = {"id": vehicle_id, "position": point, "x": point[0], "y": point[1],
                                                 "type": "car", "color": int(uniform(seed, "car-color", leader)*8),
                                                 "state": "parked", "occupant_ids": [], "driver_id": None,
                                                 "capacity": max(4, len(members)), "heading": 0.0, "lane_offset_m": 1.6, "speed_mps": 0.0,
                                                 "parking_id": parking["id"], "owner_id": leader}
                    self._parking_reserved[parking["id"]] += 1
                self.units.append(unit)
                for key in members:
                    self.unit_for[key] = unit
        # Transit owns real passengers; an operator is not invented as a resident.
        if transit_enabled:
            from .campus_transit import CampusTransit
            self.transit = CampusTransit(self, campus_day_type)
        if start_minute:
            self.step(float(start_minute)*60)
        self._reset_recording()

    @property
    def minute(self):
        return self.elapsed_seconds/60 % 1440

    def _reset_recording(self):
        self._frame_start = self.elapsed_seconds
        self._frame_seconds = 0.0
        self._motions = {p["id"]: [(0.0, tuple(p["position"]))] for p in self.people}
        self._vehicle_motions = {key: [(0.0, tuple(v["position"]))] for key, v in self.vehicles.items()}
        self._vehicle_visibility = [{"id": key, "at": 0.0, "visible": bool(v.get("service_active"))}
                                    for key, v in self.vehicles.items() if v.get("type") == "bus"]
        self._transitions = []
        self._vehicle_states = []
        self._last_vehicle_states = {}
        self._changed_routes = set()
        for p in self.people:
            self._record_activity(p, 0.0)
        for vehicle in self.vehicles.values():
            self._record_vehicle(vehicle, 0.0)

    def _record_activity(self, person, at):
        self._transitions.append({"id": person["id"], "at": at,
                                  **{key: person[key] for key in ("mode", "vehicle_id", "inside", "activity", "place_id", "movement_style", "speed_mps", "weather_response")}})

    def _record_vehicle(self, vehicle, at):
        state = {"state": vehicle["state"], "speed_mps": round(vehicle.get("speed_mps", 0.), 3),
                 "weather_response": vehicle.get("weather_response", "none")}
        if self._last_vehicle_states.get(vehicle["id"]) != state:
            self._vehicle_states.append({"id": vehicle["id"], "at": at, **state})
            self._last_vehicle_states[vehicle["id"]] = state

    def _movement(self, unit, speed, style=None, response=None):
        """Record a physical gait without changing the selected destination."""
        response = self.weather["response"] if response is None else response
        style = ("careful" if response == "snow_caution" else "walk") if style is None else style
        if speed <= 1e-8 and style not in {"brace", "recover"}:
            style = "still"
        for key in unit["members"]:
            person = self.people[key]
            actual_response = "none" if person["inside"] else response
            values = (style, round(speed, 3), actual_response)
            if values != (person["movement_style"], person["speed_mps"], person["weather_response"]):
                person.update(movement_style=style, speed_mps=values[1], weather_response=actual_response)
                self._record_activity(person, self._event_time-self._frame_start)

    def walking_pace(self, unit, factor=1.):
        response = self.weather["response"]
        pace, style = unit["speed"]*factor*self.weather["walk_factor"], "careful" if response == "snow_caution" else "walk"
        if unit.get("emergency_pace") and response != "snow_caution":
            # Children, older adults and mobility aids set the whole unit's pace.
            restricted = any(self.profiles[i]["age"] in {"child", "older"} or self.profiles[i]["appearance"]["mobility"] != "walk" for i in unit["members"])
            pace = min(1.55 if restricted else 2.4, pace*(1.15 if restricted else 1.65))
            style = "walk" if restricted else "run"
            if response == "none":
                response = "seeking_shelter"
        return pace, style, response

    def walking_speed(self, unit, factor=1.):
        pace, style, response = self.walking_pace(unit, factor)
        self._movement(unit, pace, style, response)
        return pace

    def _activity(self, unit, activity, mode, inside=False, place_id=None):
        for key in unit["members"]:
            p = self.people[key]
            personal_activity = activity
            if inside and not unit["override"] and activity == unit["target"]["activity"]:
                own_stop = _target(self.profiles[key], self.minute)
                if own_stop["inside"] and own_stop["place_id"] == place_id:
                    personal_activity = own_stop["activity"]
            aboard_bus = bool(self.transit and self.transit.is_aboard(unit))
            transport_id = unit.get("transit", {}).get("bus_id") if aboard_bus else unit["vehicle_id"]
            vehicle_id = transport_id if mode in {"boarding", "driving", "riding", "alighting"} else None
            actual_mode = "driving" if mode == "riding" and key == unit["leader"] and not aboard_bus else mode
            new = (personal_activity, actual_mode, inside, place_id, vehicle_id)
            old = (p["activity"], p["mode"], p["inside"], p["place_id"], p["vehicle_id"])
            p.update(activity=personal_activity, mode=actual_mode, inside=inside, place_id=place_id, vehicle_id=vehicle_id)
            if actual_mode not in {"walking", "riding", "driving"}:
                p.update(movement_style="still", speed_mps=0.0, weather_response="none" if inside else self.weather["response"])
            if new != old:
                self._record_activity(p, self._event_time-self._frame_start)

    def _clear_segment(self, start, end, blocked):
        return segment_is_clear(start, end, blocked, self.city.meters_per_unit)

    def _path(self, position, target, unit, driving=False, blocked=None):
        graph = self.city.vehicle_graph if driving else self.city.graph
        position, target = tuple(position), tuple(target)
        if target not in graph:
            return None
        if position == target:
            return [position]
        anchors = [position] if position in graph else [p for p in (unit.get("edge_end"), unit.get("edge_start")) if p in graph]
        if driving and position not in graph:
            anchors = anchors[:1]  # A car cannot reverse against a directed edge.
        if not anchors:
            return None
        def valid_edge(a, b):
            meta = graph.get_edge_data(a, b)
            return not (unit["no_steps"] and not driving and meta.get("steps")) and self._clear_segment(a, b, blocked)
        # Egress permission is directional even on a two-way footpath. A
        # directed view keeps bidirectional Dijkstra's reverse search honest.
        routing_graph = graph.to_directed(as_view=True) if blocked and not graph.is_directed() else graph
        view = nx.subgraph_view(routing_graph, filter_edge=valid_edge) if blocked or (unit["no_steps"] and not driving) else graph
        best = None
        for anchor in anchors:
            if not self._clear_segment(position, anchor, blocked):
                continue
            cache_key = (anchor, target, driving, unit["no_steps"])
            try:
                if cache_key not in self._paths:
                    base = nx.subgraph_view(graph, filter_edge=lambda a, b: not graph[a][b].get("steps")) if unit["no_steps"] and not driving else graph
                    tree_key = (target, driving, unit["no_steps"])
                    if not driving and target not in self._frequent_targets:
                        route = nx.shortest_path(base, anchor, target, weight="weight")
                    else:
                        if tree_key not in self._path_trees:
                            search = base.reverse(copy=False) if base.is_directed() else base
                            predecessors, _ = nx.dijkstra_predecessor_and_distance(search, target, weight="weight")
                            if len(self._path_trees) >= 32:
                                self._path_trees.pop(next(iter(self._path_trees)))
                            self._path_trees[tree_key] = predecessors
                        predecessors = self._path_trees[tree_key]
                        if anchor not in predecessors:
                            continue
                        route = [anchor]
                        while route[-1] != target:
                            route.append(predecessors[route[-1]][0])
                    self._paths[cache_key] = route
                path = self._paths[cache_key]
                if blocked and not all(self._clear_segment(a, b, blocked) for a, b in pairwise(path)):
                    path = nx.shortest_path(view, anchor, target, weight="weight")
                    if not all(self._clear_segment(a, b, blocked) for a, b in pairwise(path)):
                        continue
                value = ([position] if position != anchor else []) + list(path)
                length = sum(distance(a, b) for a, b in pairwise(value))
                if best is None or length < best[0]:
                    best = length, value
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
        return best[1] if best else None

    def path_to(self, resident_id, place_id, blocked=None):
        if place_id not in self.places:
            return None
        unit = self.unit_for[resident_id]
        if self.transit and self.transit.is_aboard(unit):
            target = {**self.places[place_id], "destination": self.places[place_id]["entrance"]}
            return self.transit.path_to(unit, target, blocked)
        if self.people[resident_id]["mode"] in {"driving", "riding", "alighting"}:
            # Feasibility includes reaching a legal parking transfer first.
            options = self._parking_options(unit, self.places[place_id], blocked)
            return options[0][2] + options[0][3][1:] if options else None
        return self._path(unit["position"], self.places[place_id]["entrance"], unit, blocked=blocked)

    def can_route(self, resident_id, place_id, blocked=None):
        return self.path_to(resident_id, place_id, blocked) is not None

    def route_seconds_to(self, resident_id, place_id, blocked=None):
        """Comparable movement cost, including a legal car-to-walk transfer.

        Current mode-specific weather speeds rank alternatives; this is not a
        traffic ETA and does not predict queues, future weather or boarding delay.
        """
        if place_id not in self.places:
            return None
        unit = self.unit_for[resident_id]
        if self.transit and self.transit.is_aboard(unit):
            target = {**self.places[place_id], "destination": self.places[place_id]["entrance"]}
            return self.transit.route_seconds_to(unit, target, blocked)
        if self.people[resident_id]["mode"] in {"driving", "riding", "alighting"}:
            options = self._parking_options(unit, self.places[place_id], blocked)
            return options[0][0] if options else None
        path = self.path_to(resident_id, place_id, blocked)
        if path is None:
            return None
        return sum(distance(a, b) for a, b in pairwise(path))*self.city.meters_per_unit/self.walking_pace(unit)[0]

    def _parking_options(self, unit, target, blocked=None):
        vehicle = self.vehicles[unit["vehicle_id"]]
        options = []
        for parking in self.city.parking:
            already_reserved = parking["id"] in {vehicle.get("parking_id"), unit.get("destination_parking")}
            if self._parking_reserved[parking["id"]] >= parking["capacity"] and not already_reserved:
                continue
            point = tuple(parking["position"])
            car_path = self._path(vehicle["position"], point, unit, True, blocked)
            walk_path = self._path(point, target["entrance"], unit, blocked=blocked)
            if car_path and walk_path:
                car_seconds = sum(distance(a, b) for a, b in pairwise(car_path))*self.city.meters_per_unit/(6*self.weather["vehicle_factor"])
                walk_seconds = sum(distance(a, b) for a, b in pairwise(walk_path))*self.city.meters_per_unit/self.walking_pace(unit)[0]
                options.append((car_seconds+walk_seconds, parking, car_path, walk_path))
        return sorted(options, key=lambda row: row[0])

    def route_to(self, resident_id, place_id, activity="seeking shelter", blocked=None):
        unit = self.unit_for[resident_id]
        if unit["override"] and resident_id != unit["leader"] and unit["target"]["place_id"] != place_id:
            return False
        if not self.can_route(resident_id, place_id, blocked):
            return False
        place = self.places[place_id]
        target = {"place_id": place_id, "activity": activity, "inside": place["solid_building"], "destination": place["entrance"]}
        unit["override"], unit["held"] = True, False
        self._begin(unit, target, blocked, emergency=True)
        return unit["stage"] != "unreachable"

    def hold(self, resident_id, activity="waiting"):
        unit = self.unit_for[resident_id]
        unit["held"] = True
        unit["override"] = True
        unit["emergency_pace"] = False
        if self.transit and self.transit.is_aboard(unit):
            # A passenger intention cannot stop a public bus independently.
            # Transit continues to own physical motion and legal alighting.
            return
        if self.transit:
            self.transit.cancel(unit)
        for key in unit["members"]:
            p = self.people[key]
            p["activity"] = activity
            self._record_activity(p, self.elapsed_seconds-self._frame_start)
        self._event_time = self.elapsed_seconds
        self._movement(unit, 0.)
        if unit["vehicle_id"] and self.vehicles[unit["vehicle_id"]]["occupant_ids"]:
            vehicle = self.vehicles[unit["vehicle_id"]]
            unit["current_speed"] = 0.
            vehicle.update(state="waiting", speed_mps=0.)
            self._record_vehicle(vehicle, self.elapsed_seconds-self._frame_start)

    def interrupt(self, resident_id, until_seconds, activity="bracing against the wind"):
        """Temporary physical interruption; preserve the chosen trip and seats."""
        unit = self.unit_for[resident_id]
        unit["impact_until"] = max(unit.get("impact_until", 0), float(until_seconds))
        unit["impact_activity"] = activity
        if unit["stage"] == "driving":
            unit["current_speed"] = 0.0
            vehicle = self.vehicles[unit["vehicle_id"]]
            vehicle.update(speed_mps=0.0, state="yielding", weather_response="wind_impact")
            self._record_vehicle(vehicle, self.elapsed_seconds-self._frame_start)
        if unit.get("impact_prior") is None:
            p = self.people[unit["leader"]]
            unit["impact_prior"] = (p["activity"], "riding" if p["mode"] == "driving" else p["mode"], p["inside"], p["place_id"])
        self._event_time = self.elapsed_seconds
        person = self.people[unit["leader"]]
        self._activity(unit, activity, ("riding" if person["mode"] == "driving" else person["mode"]) if person["vehicle_id"] else "waiting", person["inside"], person["place_id"])
        self._movement(unit, 0., "recover" if activity == "recovering from wind impact" else "brace", "wind_impact")

    def resume(self, resident_id):
        unit = self.unit_for[resident_id]
        unit["override"], unit["held"] = False, False
        unit["emergency_pace"] = False
        unit["next_agenda_seconds"] = 0
        if unit["stage"] == "activity":
            unit["target"] = None

    def _reserve_destination(self, unit, parking):
        vehicle = self.vehicles[unit["vehicle_id"]]
        old = unit.get("destination_parking")
        if old and old != vehicle.get("parking_id"):
            self._parking_reserved[old] -= 1
        unit["destination_parking"] = parking["id"]
        if parking["id"] != vehicle.get("parking_id"):
            self._parking_reserved[parking["id"]] += 1

    def _begin(self, unit, target, blocked=None, emergency=False):
        self._changed_routes.update(unit["members"])
        unit["emergency_pace"] = bool(emergency)
        previous_override = unit["override"]
        if self.transit and self.transit.route_to(unit, target, blocked) is True:
            unit["target"] = target
            unit["override"] = previous_override or emergency
            for key in unit["members"]:
                self.people[key]["destination_place_id"] = target["place_id"]
            return
        unit["target"] = target
        unit["held"] = False
        for key in unit["members"]:
            self.people[key]["destination_place_id"] = target["place_id"]
        place = self.places[target["place_id"]]
        vehicle = self.vehicles.get(unit["vehicle_id"])
        if vehicle and not vehicle["occupant_ids"] and unit.get("destination_parking"):
            reserved = unit.pop("destination_parking")
            if reserved != vehicle.get("parking_id"):
                self._parking_reserved[reserved] -= 1
            vehicle["state"] = "parked"
        if vehicle and vehicle["occupant_ids"]:
            options = self._parking_options(unit, place, blocked)
            if options:
                _, parking, car_path, _ = options[0]
                self._reserve_destination(unit, parking)
                unit.update(stage="driving", route=car_path)
                vehicle["state"] = "driving"
                self._activity(unit, "driving to a safe stop" if emergency else "travelling by car", "riding")
                return
            unit.update(stage="unreachable", route=[], held=True)
            vehicle.update(state="waiting", speed_mps=0.)
            unit["current_speed"] = 0.
            self._activity(unit, "waiting for a reachable parking stop", "riding")
            return
        walk_path = self._path(unit["position"], target["destination"], unit, blocked=blocked)
        if not walk_path:
            unit.update(stage="unreachable", route=[])
            self._activity(unit, "waiting for an accessible route", "waiting", self.people[unit["leader"]]["inside"], self.people[unit["leader"]]["place_id"])
            return
        # Emergency sheltering prioritizes a nearby building; never walk to a
        # parked car just because that household happens to own one.
        walk_metres = sum(distance(a, b) for a, b in pairwise(walk_path))*self.city.meters_per_unit
        if vehicle and not emergency and walk_metres > 300:
            options = self._parking_options(unit, {**place, "entrance": target["destination"]}, blocked)
            to_car = self._path(unit["position"], vehicle["position"], unit, blocked=blocked)
            if options and to_car and options[0][1]["id"] != vehicle.get("parking_id"):
                approach_seconds = sum(distance(a, b) for a, b in pairwise(to_car))*self.city.meters_per_unit/self.walking_pace(unit)[0]
                # Include walking back to the car, both transfers and the last
                # walk. A 10% margin avoids trivial drives between classes.
                if approach_seconds + options[0][0] + 30 < .9*walk_metres/self.walking_pace(unit)[0]:
                    self._reserve_destination(unit, options[0][1])
                    unit.update(stage="walk_to_car", route=to_car, car_route=options[0][2])
                    self._activity(unit, "walking to the car", "walking")
                    return
        if self.transit and not emergency and self.transit.try_trip(unit, target, walk_path, blocked):
            return
        unit.update(stage="walking", route=walk_path)
        self._activity(unit, activity=f"walking to {target.get('venue_name') or place['name']}", mode="walking")

    def _move(self, unit, seconds, speed, driving, blocked):
        route = unit["route"]
        start_pos = tuple(unit["position"])
        budget = speed*seconds/self.city.meters_per_unit
        traversed = [(0.0, start_pos, unit["heading"])]
        travelled = 0.0
        while route and budget > 1e-9:
            if distance(unit["position"], route[0]) < 1e-8:
                route.pop(0)
                continue
            end = route[0]
            start = tuple(unit["position"])
            length = distance(start, end)
            if not self._clear_segment(start, end, blocked):
                unit["held"] = True
                if driving:
                    self.vehicles[unit["vehicle_id"]].update(state="waiting", speed_mps=0.)
                    unit["current_speed"] = 0.
                self._event_time = self.elapsed_seconds+travelled*self.city.meters_per_unit/max(speed, .001)
                self._activity(unit, "route closed — waiting", "riding" if driving else "waiting")
                self._movement(unit, 0.)
                if driving:
                    self._record_vehicle(self.vehicles[unit["vehicle_id"]], self._event_time-self._frame_start)
                break
            allowed_m, wait_reason = self.traffic.allowance(unit, start, end, min(budget, length)*self.city.meters_per_unit, speed, driving)
            move = min(budget, length, allowed_m/self.city.meters_per_unit)
            if move < 1e-9:
                unit["traffic_wait"] = wait_reason or "waiting for traffic"
                self._event_time = self.elapsed_seconds+travelled*self.city.meters_per_unit/speed
                if self.transit and unit["stage"] in {"boarding_bus", "alighting_bus"}:
                    self.transit._activity(unit, unit["traffic_wait"], "boarding" if unit["stage"] == "boarding_bus" else "alighting", unit["transit"]["bus_id"])
                else:
                    self._activity(unit, unit["traffic_wait"], "riding" if driving else "waiting")
                if driving:
                    self.vehicles[unit["vehicle_id"]].update(state="yielding", speed_mps=0.0)
                    unit["current_speed"] = 0.0
                    self._record_vehicle(self.vehicles[unit["vehicle_id"]], self._event_time-self._frame_start)
                self._movement(unit, 0.)
                self.traffic.wait_events += 1
                break
            if unit.get("traffic_wait"):
                unit["traffic_wait"] = None
                name = unit["target"].get("venue_name") or self.places.get(unit["target"].get("place_id"), {}).get("name", "the next stop")
                self._event_time = self.elapsed_seconds+travelled*self.city.meters_per_unit/speed
                if self.transit and unit["stage"] in {"boarding_bus", "alighting_bus"}:
                    self.transit._activity(unit, "boarding the campus shuttle" if unit["stage"] == "boarding_bus" else "leaving the campus shuttle", "boarding" if unit["stage"] == "boarding_bus" else "alighting", unit["transit"]["bus_id"])
                else:
                    self._activity(unit, ("riding the campus shuttle" if str(unit["vehicle_id"]).startswith("bus-") else "travelling by car") if driving else f"walking to {name}", "riding" if driving else "walking")
                if driving:
                    self.vehicles[unit["vehicle_id"]]["state"] = "driving"
            if start in (self.city.vehicle_graph if driving else self.city.graph):
                unit["edge_start"] = start
            unit["edge_end"] = end
            point = tuple(start[i] + (end[i]-start[i])*move/length for i in (0, 1))
            unit["heading"] = math.atan2(end[1]-start[1], end[0]-start[0])
            unit["position"] = point
            travelled += move
            budget -= move
            traversed.append((travelled*self.city.meters_per_unit/speed, point, unit["heading"]))
            if move >= length-1e-8:
                unit["position"] = tuple(end)
                route.pop(0)
        base_at = self.elapsed_seconds-self._frame_start
        if len(traversed) > 1:
            # Preserve stationary time before a trip starts within this frame.
            for key in unit["members"]:
                self._motions[key].append((base_at, tuple(self.people[key]["position"])))
            if driving:
                self._vehicle_motions[unit["vehicle_id"]].append((base_at, start_pos))
        for at, point, heading in traversed[1:]:
            for key in unit["members"]:
                self._motions[key].append((base_at+at, self._formation_point(unit, point, key, heading, driving)))
            if driving:
                self._vehicle_motions[unit["vehicle_id"]].append((base_at+at, point))
        for key in unit["members"]:
            p = self.people[key]
            p["position"] = self._formation_point(unit, unit["position"], key, unit["heading"], driving)
            if not driving:
                p["walked_m"] += travelled*self.city.meters_per_unit
        if driving:
            vehicle = self.vehicles[unit["vehicle_id"]]
            vehicle.update(position=tuple(unit["position"]), x=unit["position"][0], y=unit["position"][1])
            if distance(start_pos, unit["position"]) > 0:
                vehicle["heading"] = math.atan2(unit["position"][1]-start_pos[1], unit["position"][0]-start_pos[0])
        if not route:
            self._event_time = self.elapsed_seconds + travelled*self.city.meters_per_unit/speed
        return not route

    def _formation_point(self, unit, point, resident_id, heading, driving):
        if driving or len(unit["members"]) == 1:
            return tuple(point)
        # Household members occupy distinct positions within the authored 3 m
        # walkway corridor. This is authoritative state, not renderer jitter.
        index = unit["members"].index(resident_id)
        metres = (index - (len(unit["members"])-1)/2)*.65
        offset = metres/self.city.meters_per_unit
        candidate = (point[0]-math.sin(heading)*offset, point[1]+math.cos(heading)*offset)
        return tuple(point) if self._blocked and self._blocked(candidate) else candidate

    def _arrive(self, unit):
        target = unit["target"]
        if target["inside"]:
            place_id = target["place_id"]
            occupied = sum(p["inside"] and p["place_id"] == place_id and p["id"] not in unit["members"] for p in self.people)
            admitted = occupied + len(unit["members"]) <= self.places[place_id]["capacity"]
            if self._admit:
                admitted = admitted and self._admit(list(unit["members"]), place_id)
            if not admitted:
                unit["stage"] = "admission_wait"
                self._activity(unit, "building at capacity", "waiting", False, place_id)
                return
        unit["stage"] = "activity"
        self._activity(unit, target["activity"], "indoors" if target["inside"] else "waiting", target["inside"], target["place_id"])

    def _prepare_schedule(self, unit, blocked):
        if unit.get("impact_until", 0) > self.elapsed_seconds or unit["held"] or unit["override"]:
            return
        if self.elapsed_seconds+1e-8 < unit.get("next_agenda_seconds", 0):
            return
        profile = self.profiles[unit["leader"]]
        day = math.floor(self.elapsed_seconds/86400)
        following = [row["start_minute"]*60 for row in profile["routine"] if row["start_minute"]*60 > self.elapsed_seconds % 86400+1e-8]
        unit["next_agenda_seconds"] = day*86400+(min(following) if following else 86400)
        target = _target(profile, self.minute)
        if target is not unit["target"]:
            same_destination = unit["target"] and target["place_id"] == unit["target"]["place_id"] and target["destination"] == unit["target"]["destination"]
            if same_destination and unit["stage"] == "activity":
                unit["target"] = target
                self._arrive(unit)
            else:
                self._begin(unit, target, blocked)

    def _step_unit(self, unit, seconds, blocked, speed_factor):
        self._event_time = self.elapsed_seconds
        if unit.get("impact_until", 0) > self.elapsed_seconds:
            return
        if unit.get("impact_prior"):
            prior = unit.pop("impact_prior")
            if self.people[unit["leader"]]["activity"] == unit.get("impact_activity"):
                self._activity(unit, *prior)
            unit.pop("impact_until", None)
            self._movement(unit, 0.)
            if unit["stage"] == "driving":
                vehicle = self.vehicles[unit["vehicle_id"]]
                vehicle.update(state="waiting" if unit["held"] else "driving", speed_mps=0., weather_response=self.weather["response"])
                self._record_vehicle(vehicle, self.elapsed_seconds-self._frame_start)
        if self.transit and self.transit.step_unit(unit, seconds, blocked, speed_factor):
            return
        if unit["held"]:
            return
        stage = unit["stage"]
        self._event_time = self.elapsed_seconds + seconds
        if stage in {"walking", "walk_to_car"}:
            self._event_time = self.elapsed_seconds
            done = self._move(unit, seconds, self.walking_speed(unit, speed_factor), False, blocked)
            if done:
                if stage == "walk_to_car":
                    unit.update(stage="boarding", timer=15.0)
                    self.vehicles[unit["vehicle_id"]]["state"] = "boarding"
                    self._activity(unit, "boarding the car", "boarding")
                else:
                    self._arrive(unit)
        elif stage == "boarding":
            unit["timer"] -= seconds
            if unit["timer"] <= 0:
                v = self.vehicles[unit["vehicle_id"]]
                if len(unit["members"]) > v["capacity"]:
                    raise RuntimeError("Vehicle capacity exceeded")
                v.update(occupant_ids=list(unit["members"]), driver_id=unit["leader"], state="driving")
                for key in unit["members"]:
                    self.people[key]["position"] = tuple(v["position"])
                    self._motions[key].append((self._event_time-self._frame_start, tuple(v["position"])))
                if v["parking_id"]:
                    self._parking_reserved[v["parking_id"]] -= 1
                v["parking_id"] = None
                unit.update(stage="driving", route=list(unit["car_route"]))
                self._changed_routes.update(unit["members"])
                self._activity(unit, "travelling by car", "riding")
        elif stage == "driving":
            self._event_time = self.elapsed_seconds
            speed = self.traffic.driving_speed(unit, 6.0*speed_factor*self.weather["vehicle_factor"], seconds)
            unit["current_speed"] = speed
            vehicle = self.vehicles[unit["vehicle_id"]]
            vehicle.update(speed_mps=speed, state="driving", weather_response=self.weather["response"])
            self._record_vehicle(vehicle, self._event_time-self._frame_start)
            self._movement(unit, speed, "still")
            if self._move(unit, seconds, speed, True, blocked):
                v = self.vehicles[unit["vehicle_id"]]
                v.update(state="alighting", parking_id=unit.get("destination_parking"), speed_mps=0.)
                unit["current_speed"] = 0.
                self._record_vehicle(v, self._event_time-self._frame_start)
                unit.update(stage="alighting", timer=15.0)
                self._activity(unit, "leaving the car", "alighting")
        elif stage == "alighting":
            unit["timer"] -= seconds
            if unit["timer"] <= 0:
                v = self.vehicles[unit["vehicle_id"]]
                v.update(occupant_ids=[], driver_id=None, state="parked")
                unit["destination_parking"] = None
                path = self._path(unit["position"], unit["target"]["destination"], unit, blocked=blocked)
                unit.update(stage="walking" if path else "unreachable", route=path or [])
                self._changed_routes.update(unit["members"])
                name = unit['target'].get('venue_name') or self.places[unit['target']['place_id']]['name']
                self._activity(unit, f"walking to {name}" if path else "waiting for an accessible route", "walking" if path else "waiting")
        elif stage == "admission_wait":
            self._arrive(unit)

    def step(self, seconds, blocked=None, speed_factor=1.0, admit=None, before_substep=None, after_substep=None, max_step_seconds=5, weather=None):
        if not math.isfinite(seconds) or seconds < 0 or (not callable(speed_factor) and not 0 < speed_factor <= 3) or not math.isfinite(max_step_seconds) or max_step_seconds <= 0:
            raise ValueError("Invalid campus time or speed factor")
        self._reset_recording()
        self._blocked = blocked
        self._admit = admit
        remaining = float(seconds)
        while remaining > 1e-8:
            self._event_time = self.elapsed_seconds
            for unit in self.units:
                self._prepare_schedule(unit, blocked)
            bus_units = self.transit.traffic_units() if self.transit else []
            traffic_active = bool(bus_units) or any(u["stage"] == "driving" for u in self.units)
            quantum = min(max_step_seconds, 1.0 if traffic_active else 5.0)
            dt = min(quantum-self.elapsed_seconds % quantum, remaining)
            if before_substep:
                before_substep(self.elapsed_seconds, dt)
            factor = speed_factor() if callable(speed_factor) else speed_factor
            if not math.isfinite(factor) or not 0 < factor <= 3:
                raise ValueError("Invalid campus speed factor")
            self.weather = weather() if callable(weather) else weather or {"response": "none", "walk_factor": 1., "vehicle_factor": 1., "headway_seconds": 1.2, "traction": 1.}
            for unit in [*self.units, *bus_units]:
                unit["_traffic_speed"] = 6.*factor*self.weather["vehicle_factor"] if unit["stage"] == "driving" or unit.get("traffic_id") else self.walking_pace(unit, factor)[0]
            self.traffic.begin([*self.units, *bus_units], self.vehicles, self.elapsed_seconds, dt, factor,
                               self.weather["headway_seconds"], self.weather["traction"])
            for unit in self.units:
                self._step_unit(unit, dt, blocked, factor)
            if self.transit:
                self.transit.step(dt, blocked, factor)
            for vehicle in self.vehicles.values():
                self._record_vehicle(vehicle, self.elapsed_seconds+dt-self._frame_start)
            self.elapsed_seconds += dt
            remaining -= dt
            if after_substep:
                after_substep(self.elapsed_seconds, dt)
            if abs(self.elapsed_seconds % 60) < 1e-8:
                self._update_meetings()
        self._frame_seconds = float(seconds)
        self.tick += 1
        if abs(self.elapsed_seconds % 60) > 1e-8:
            self._update_meetings()

    def _update_meetings(self):
        for p in self.people:
            p["partner_ids"] = []
        for key, meeting in list(self._meetings.items()):
            members = [self.people[i] for i in meeting["agent_ids"]]
            if meeting["ends_at"] < self.elapsed_seconds or any(p["inside"] or p["place_id"] != meeting["place_id"] for p in members):
                self._meeting_cooldown[tuple(meeting["agent_ids"])] = self.elapsed_seconds+900
                del self._meetings[key]
        already = {i for m in self._meetings.values() for i in m["agent_ids"]}
        for p in self.people:
            if p["id"] in already or p["inside"] or p["mode"] != "waiting" or not p["place_id"]:
                continue
            friend = next((self.people[i] for i in self.profiles[p["id"]]["social_connections"]
                           if i not in already and self.people[i]["place_id"] == p["place_id"] and
                           not self.people[i]["inside"] and self.people[i]["mode"] == "waiting" and
                           self._meeting_cooldown.get(tuple(sorted([p["id"], i])), 0) <= self.elapsed_seconds and
                           distance(p["position"], self.people[i]["position"])*self.city.meters_per_unit < 6), None)
            if friend:
                ids = sorted([p["id"], friend["id"]])
                key = f"meeting-{ids[0]}-{ids[1]}-{int(self.elapsed_seconds)}"
                self._meetings[key] = {"id": key, "kind": "conversation", "agent_ids": ids,
                                       "position": list(p["position"]), "place_id": p["place_id"],
                                       "starts_at": self.elapsed_seconds, "ends_at": self.elapsed_seconds+240}
                already.update(ids)
        for meeting in self._meetings.values():
            for i in meeting["agent_ids"]:
                self.people[i]["partner_ids"] = [j for j in meeting["agent_ids"] if i != j]

    def _motion_rows(self, source):
        duration = self._frame_seconds
        if duration <= 0:
            return []
        rows = []
        for key, samples in source.items():
            if len(samples) < 2:
                continue
            dedup = []
            for at, point in samples:
                at = max(0.0, min(duration, at))
                if dedup and at <= dedup[-1][0]+1e-8:
                    dedup[-1] = (at, point)
                else:
                    dedup.append((at, point))
            if not dedup or dedup[0][0] > 0:
                continue
            if dedup[-1][0] < duration:
                dedup.append((duration, dedup[-1][1]))
            # Remove only constant-velocity collinear samples. Corners, pauses,
            # route changes and boarding times remain exact in the recording.
            compact = []
            for sample in dedup:
                while len(compact) >= 2:
                    a, b = compact[-2:]
                    interval = sample[0]-a[0]
                    fraction = (b[0]-a[0])/interval if interval else 0
                    expected = tuple(a[1][i]+(sample[1][i]-a[1][i])*fraction for i in (0, 1))
                    if distance(expected, b[1]) > 1e-7:
                        break
                    compact.pop()
                compact.append(sample)
            if len(compact) >= 2 and any(distance(p, compact[0][1]) > 1e-8 for _, p in compact):
                rows.append({"id": key, "path": [[round(v, 6) for v in p] for _, p in compact],
                             "fractions": [round(t/duration, 7) for t, _ in compact]})
        return rows

    def frame(self, tick=None, time=None):
        tick = self.tick if tick is None else tick
        activity_keys = ("id", "activity", "place_id", "destination_place_id", "inside", "partner_ids",
                         "mode", "vehicle_id", "group_id", "walked_m", "movement_style", "speed_mps", "weather_response")
        changed_vehicle_ids = {key for key, count in Counter(row["id"] for row in self._vehicle_states).items() if count > 1}
        changed_activity_ids = {key for key, count in Counter(row["id"] for row in self._transitions).items() if count > 1}
        transitions = [{k: v for k, v in row.items() if k != "at"} |
                       {"fraction": min(1.0, max(0.0, row["at"]/self._frame_seconds)) if self._frame_seconds else 0.0}
                       for row in self._transitions if row["id"] in changed_activity_ids]
        accessible = {unit["id"]: bool(unit["route"]) and unit["stage"] not in {"unreachable", "admission_wait"} and
                      any(distance(a, b) > 1e-8 for a, b in pairwise([unit["position"], *unit["route"]])) and
                      (not self._blocked or all(self._clear_segment(a, b, self._blocked)
                                               for a, b in pairwise([unit["position"], *unit["route"]])))
                      for unit in self.units}
        return {
            "tick": tick, "time": self.elapsed_seconds if time is None else time,
            "world_clock_minutes": self.minute,
            "agents": [[p["id"], *p["position"], 0, 0] for p in self.people],
            "agent_activities": [{**{k: deepcopy(p[k]) for k in activity_keys},
                                  "route_accessible": accessible[self.unit_for[p["id"]]["id"]]} for p in self.people],
            "agent_activity_transitions": transitions,
            "vehicle_state_transitions": [{k: v for k, v in row.items() if k != "at"} |
                                          {"fraction": min(1., max(0., row["at"]/self._frame_seconds)) if self._frame_seconds else 0.}
                                          for row in self._vehicle_states if row["id"] in changed_vehicle_ids],
            "vehicle_visibility_transitions": [{"id": row["id"], "visible": row["visible"],
                                                 "fraction": min(1.0, max(0.0, row["at"]/self._frame_seconds)) if self._frame_seconds else 0.0}
                                                for row in self._vehicle_visibility],
            "agent_motion": self._motion_rows(self._motions), "vehicle_motion": self._motion_rows(self._vehicle_motions),
            "vehicles": [{**deepcopy(v), "position": list(v["position"])} for v in self.vehicles.values()],
            "route_changes": [{"id": p["id"], "path": [list(p["position"])] + [list(v) for v in self.unit_for[p["id"]]["route"]],
                               "destination": list(self.unit_for[p["id"]]["target"]["destination"]) if self.unit_for[p["id"]]["target"] else None} for p in self.people if not self._frame_seconds or p["id"] in self._changed_routes],
            "interactions": [{**deepcopy(m), "tick": tick, "expires_tick": tick+2} for m in self._meetings.values()],
            "hazard_cells": [], "active_hazard_cells": [], "blocked_roads": [], "metrics": zero_metrics(len(self.people)),
            "traffic": self.traffic.snapshot(),
            **(self.transit.frame_fields() if self.transit else {}),
            "town_summary": {"inside": sum(p["inside"] for p in self.people),
                             "activities": dict(Counter(p["activity"] for p in self.people)),
                             "moving_vehicles": sum(v["state"] == "driving" for v in self.vehicles.values())},
        }


_day_generation_lock = threading.Lock()


def campus_day(population=300, seed=42, disaster_type="flood", campus_day_type="teaching", transit_enabled=True):
    # Hazards do not change the ordinary day. Keep only two population/seed
    # recordings, rather than retaining duplicate days for every disaster tab.
    # lru_cache alone allows duplicate computation on concurrent cache misses.
    # A browser reload and a preview request should share one expensive day.
    with _day_generation_lock:
        return _campus_day(population, seed, campus_day_type, transit_enabled)


@lru_cache(maxsize=2)
def _campus_day(population, seed, campus_day_type="teaching", transit_enabled=True):
    life = CampusLife(population, seed, campus_day_type=campus_day_type, transit_enabled=transit_enabled)
    frames = [life.frame(0)]
    for tick in range(1, DAY_TICKS):
        life.step(MINUTES_PER_TICK*60)
        frames.append(life.frame(tick))
    return {"city": {**life.city.serialize(), "art_seed": seed, "art_manifest_version": "last-warning-campus/2"},
            "states": STATES, "profiles": life.profiles, "households": life.households,
            "frames": frames, "total": DAY_TICKS, "town_day_version": DAY_VERSION,
            "minutes_per_tick": MINUTES_PER_TICK, "clock_start_minutes": 0,
            "campus_day_type": campus_day_type, "transit_enabled": transit_enabled,
            "recording_version": "last-warning-recording/3", "art_seed": seed,
            "art_manifest_version": "last-warning-campus/2"}
