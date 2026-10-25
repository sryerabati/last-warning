"""Deterministic town itineraries on the canonical graph; no cloud calls.

Day time is compressed to five minutes per recorded frame. An indoor resident
occupies a named building; its logical routing position remains that building's
entrance. Interior geometry, room occupancy and building damage are not modeled.
"""
from collections import Counter, defaultdict
from functools import lru_cache

import networkx as nx

from ..schemas import ScenarioConfig
from .world import make_city, uniform

DAY_TICKS = 288
MINUTES_PER_TICK = 5
DAY_VERSION = "riverside-life/1"
FIRST_NAMES = ("Alex", "Maya", "Sam", "Nora", "Leo", "Ava", "Theo", "Iris", "Eli", "Lena", "Owen", "Zoe",
               "Kai", "Mila", "Noah", "Ruby", "Finn", "Ada", "Arlo", "Esme", "Jules", "Remy", "Sage", "Robin")
SURNAMES = ("Reed", "Foster", "Brooks", "Ellis", "Morgan", "Hayes", "Bennett", "Park", "Rivera", "Patel",
            "Chen", "Campbell", "Morris", "Walsh", "Santos", "Lewis")


def routine_target(profile, minute):
    minute %= 1440
    return next(row for row in reversed(profile["routine"]) if row["start_minute"] <= minute)


def make_profiles(config, city):
    homes = [p for p in city.places if p["kind"] == "home"]
    if not homes:
        raise ValueError("Town life requires an organic town with homes")
    places_by_kind = {kind: [p for p in city.places if p["kind"] == kind]
                      for kind in ("work", "school", "civic", "shop", "park")}
    social = nx.watts_strogatz_graph(config.population, 6, .12, seed=config.seed)
    profiles = []
    for resident_id in range(config.population):
        household = resident_id // 4
        home = homes[household % len(homes)]
        role = ("worker", "worker", "student", "neighbor")[resident_id % 4]

        def choose(kind, salt, key=resident_id):
            values = places_by_kind[kind]
            return values[int(uniform(config.seed, salt, key) * len(values))]

        work = choose("school" if role == "student" else "work", "workplace") if role != "neighbor" else None
        market, park, civic = choose("shop", "market"), choose("park", "park"), choose("civic", "civic")
        # Exact five-minute departures make a day snapshot unambiguous.
        offset = int(uniform(config.seed, "departure", resident_id) * 6) * 5
        routine = []

        def at(minute, activity, place, inside, key=resident_id, visits=routine):
            spots = place.get("activity_spots") or [place["entrance"]]
            spot = spots[int(uniform(config.seed, "activity-spot", key, place["id"]) * len(spots))]
            visits.append({"start_minute": minute, "activity": activity, "place_id": place["id"],
                            "inside": inside, "destination": list(spot)})

        at(0, "sleeping", home, True)
        at(390 + offset, "at home", home, True)
        if role in {"worker", "student"}:
            at(430 + offset, "studying" if role == "student" else "working", work, True)
            at(700 + offset, "shopping", market, False)
            at(790 + offset, "studying" if role == "student" else "working", work, True)
            at(940 + offset if role == "student" else 980 + offset, "at home", home, True)
            at(1050 + offset, "relaxing", park, False)
        else:
            at(450 + offset, "shopping", market, False)
            at(570 + offset, "relaxing", park, False)
            at(730 + offset, "at home", home, True)
            at(860 + offset, "visiting", civic, True)
            at(1020 + offset, "relaxing", park, False)
        at(1140 + offset, "at home", home, True)
        at(1290 + offset, "sleeping", home, True)
        trust = .5 + .5 * uniform(config.seed, "trust", resident_id)
        speed = .45 + .85 * uniform(config.seed, "speed", resident_id)
        family = [i for i in range(household * 4, min(config.population, household * 4 + 4)) if i != resident_id]
        neighbors = sorted(set(social.neighbors(resident_id)).union(family))
        name = (FIRST_NAMES[int(uniform(config.seed, "first-name", resident_id) * len(FIRST_NAMES))]
                + " " + SURNAMES[int(uniform(config.seed, "surname", household) * len(SURNAMES))])
        profiles.append({"id": resident_id, "name": name, "household_id": f"household-{household+1}",
                         "home_place_id": home["id"], "work_place_id": work["id"] if work else None,
                         "role": role, "goal": f"Follow my daily visits and return to my household at {home['name']}.",
                         "trust": trust, "movement_speed": speed,
                         "reaction_delay": int(6 * uniform(config.seed, "reaction", resident_id)),
                         "social_connections": neighbors, "routine": routine})
    return profiles


def interactions_for(states, tick):
    """Meetings are observable co-location, not invented dialogue or alert delivery."""
    groups = defaultdict(list)
    for key, state in enumerate(states):
        state["partner_ids"] = []
        if not state["inside"] and state["activity"] in {"shopping", "relaxing", "visiting"}:
            groups[tuple(state["position"])].append(key)
    result = []
    for position, ids in sorted(groups.items()):
        for offset in range(0, len(ids) - 1, 2):
            first, second = ids[offset:offset+2]
            states[first]["partner_ids"] = [second]
            states[second]["partner_ids"] = [first]
            result.append({"id": f"meeting-{tick}-{first}-{second}", "kind": "conversation",
                           "agent_ids": [first, second], "position": list(position),
                           "tick": tick, "expires_tick": tick + 1})
    return result


def activity_row(key, state):
    return {"id": key, "activity": state["activity"], "place_id": state["place_id"],
            "destination_place_id": state.get("destination_place_id"), "inside": state["inside"],
            "partner_ids": list(state["partner_ids"])}


def zero_metrics(population):
    return {"population": population, "warning_delivered": 0, "warning_noticed": 0,
            "evacuation_started": 0, "evacuated": 0, "exposed": 0, "stranded": 0,
            "evacuating": 0, "warning_shared": 0, "average_alert_receipt_time": None,
            "average_decision_delay": None, "average_evacuation_completion_time": None,
            "hazard_coverage": 0, "road_closures": 0, "route_replans": 0,
            "state_counts": {name: population if name == "UNAWARE" else 0 for name in
                             ["UNAWARE", "ALERTED", "DECIDING", "PREPARING", "EVACUATING", "SHELTERED", "STRANDED", "EXPOSED"]}}


@lru_cache(maxsize=4)
def town_day(population=300, seed=42, disaster_type="flood"):
    """A bounded, immutable-by-convention recording cache, independent of warning/start tick."""
    config = ScenarioConfig(population=population, seed=seed, disaster_type=disaster_type,
                            layout="organic", town_life=True)
    city = make_city(config)
    profiles = make_profiles(config, city)
    places = {p["id"]: p for p in city.places}
    states = [{"position": tuple(places[p["home_place_id"]]["entrance"]), "activity": "sleeping",
               "place_id": p["home_place_id"], "inside": True, "partner_ids": [],
               "destination_place_id": p["home_place_id"], "path": []} for p in profiles]
    paths = {}
    frames = []
    metrics = zero_metrics(population)
    for tick in range(DAY_TICKS):
        minute, motions, changes = tick * MINUTES_PER_TICK, [], []
        for profile, state in zip(profiles, states, strict=True):
            key = profile["id"]
            target = routine_target(profile, minute)
            end = tuple(target["destination"])
            changed = target["place_id"] != state["destination_place_id"]
            if changed:
                state["destination_place_id"] = target["place_id"]
                path_key = state["position"], end
                if path_key not in paths:
                    paths[path_key] = nx.shortest_path(city.graph, *path_key)
                state["path"] = list(paths[path_key])
            if state["position"] != end:
                state["inside"], state["place_id"], state["activity"] = False, None, "commuting"
                before = state["position"]
                steps = max(2, round(profile["movement_speed"] * 3))
                traversed = state["path"][:steps+1]
                state["path"] = state["path"][len(traversed)-1:]
                state["position"] = traversed[-1]
                if state["position"] != before:
                    motions.append({"id": key, "path": [list(p) for p in traversed],
                                    "fractions": [i / (len(traversed)-1) for i in range(len(traversed))]})
            if state["position"] == end:
                state.update(activity=target["activity"], place_id=target["place_id"], inside=target["inside"])
            if changed:
                remaining = state["path"] or [state["position"]]
                changes.append({"id": key, "path": [list(p) for p in remaining], "destination": list(end)})
        interactions = interactions_for(states, tick)
        counts = Counter(s["activity"] for s in states)
        frames.append({"tick": tick, "time": minute * 60, "world_clock_minutes": minute,
                       "agents": [[i, *s["position"], 0, 0] for i, s in enumerate(states)],
                       "agent_motion": motions, "route_changes": changes,
                       "agent_activities": [activity_row(i, state) for i, state in enumerate(states)],
                       "interactions": interactions, "hazard_cells": [], "active_hazard_cells": [],
                       "blocked_roads": [], "metrics": metrics,
                       "town_summary": {"inside": sum(s["inside"] for s in states), "activities": dict(counts)}})
    if any(s["position"] != tuple(places[p["home_place_id"]]["entrance"]) or not s["inside"]
           for p, s in zip(profiles, states, strict=True)):
        raise RuntimeError("Daily itineraries must return home before midnight without a loop teleport")
    return {"city": {**city.serialize(), "art_seed": seed, "art_manifest_version": "last-warning-pixel/1"},
            "states": ["UNAWARE", "ALERTED", "DECIDING", "PREPARING", "EVACUATING", "SHELTERED", "STRANDED", "EXPOSED"],
            "profiles": profiles, "frames": frames, "total": DAY_TICKS,
            "town_day_version": DAY_VERSION, "minutes_per_tick": MINUTES_PER_TICK, "clock_start_minutes": 0,
            "recording_version": "last-warning-recording/2", "art_seed": seed,
            "art_manifest_version": "last-warning-pixel/1"}
