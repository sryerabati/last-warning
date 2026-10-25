"""Explicit reproducible campus-day presets, not today's inferred calendar.

Official OSU calendar distinguishes class breaks with open offices from holidays
with offices closed. Individual agendas below remain authored synthetic lives.
"""
from copy import deepcopy

import networkx as nx

from .campus_world import distance
from .world import uniform

DAY_TYPES = ("teaching", "weekend", "class_break", "closed")
DAY_LABELS = {"teaching": "Teaching weekday", "weekend": "Weekend",
              "class_break": "Class break · offices open", "closed": "University holiday · offices closed"}


def apply_day_type(profiles, day_type, city, seed):
    if day_type not in DAY_TYPES:
        raise ValueError("Unknown campus day type")
    places = {p["id"]: p for p in city.places}
    parks = [p for p in city.places if p["kind"] == "park"]
    shops = [p for p in city.places if p["kind"] == "shop"]
    graph = getattr(city, "graph", None)
    accessible = set()
    if graph is not None and len(graph):
        step_free = nx.subgraph_view(graph, filter_edge=lambda a, b: not graph[a][b].get("steps"))
        accessible = max(nx.connected_components(step_free), key=len)
        shops = [p for p in shops if tuple(p["entrance"]) in accessible]
        parks = [p for p in parks if tuple(p["entrance"]) in accessible]
    gathering_nodes = {p["id"]: [node for node in accessible if distance(node, p["entrance"])*city.meters_per_unit <
                                 (110 if p.get("name") == "The Oval" else 70)] for p in parks} if accessible else {}
    for profile in profiles:
        profile["schedule_day_type"] = day_type
        if day_type == "teaching":
            continue
        role = profile["role"]
        # Local dependents retain caregiver-led care; no university timetable is
        # imposed on a preschool child or a neighbor.
        if role in {"child", "caregiver", "neighbor"}:
            continue
        if day_type == "class_break" and role in {"professor", "staff"}:
            for row in profile["routine"]:
                if row["activity"] in {"teaching", "office hours"}:
                    work = places[profile["work_place_id"]]
                    row.update(activity="research and office work", place_id=work["id"],
                               destination=list(work["entrance"]), inside=True)
            continue
        home = places[profile["home_place_id"]]
        key = profile["id"]
        offset = int(50*uniform(seed, "nonteaching-wake", key))
        routine = []
        def add(minute, activity, place, inside=True, routine=routine):
            routine.append({"start_minute": minute, "activity": activity, "place_id": place["id"],
                            "inside": inside, "destination": list(place["entrance"])})
        add(0, "sleeping", home)
        add(510+offset, "at home", home)
        if day_type == "class_break":
            add(600+offset, "independent study at home" if role in {"student", "graduate student"} else "at home", home)
        if shops and day_type != "closed":
            shop = min(shops, key=lambda p: uniform(seed, "nonteaching-errand", key, p["id"]))
            add(660+offset, "running a weekend errand" if day_type == "weekend" else "running an errand", shop)
            add(705+offset, "lunch at home", home)
        else:
            add(720, "lunch at home", home)
        if parks and uniform(seed, "nonteaching-outing", key) < .65:
            park = min(parks, key=lambda p: uniform(seed, "nonteaching-park", key, p["id"]))
            # Disperse even first-time visits over the same step-free mapped
            # footway network used by teaching days, never one shared park hub.
            old = next((r for r in profile["routine"] if r["place_id"] == park["id"] and not r["inside"]), None)
            nodes = gathering_nodes.get(park["id"], [])
            previous = None
            for visit, activity in enumerate(("taking an afternoon break", "enjoying the view", "resting before heading home")):
                add(900+offset+visit*8, activity, park, False)
                nearby = [node for node in nodes if previous and 18 < distance(node, previous)*city.meters_per_unit < 65]
                candidates = nearby or nodes
                if candidates:
                    previous = min(candidates, key=lambda node: uniform(seed, "nonteaching-outdoor", key, visit, node))
                    routine[-1]["destination"] = list(previous)
                elif old:
                    routine[-1]["destination"] = deepcopy(old["destination"])
            add(930+offset, "at home", home)
        add(1260+offset, "sleeping", home)
        profile["routine"] = routine
    return profiles


def service_headway(day_type, minute):
    """Published CC service windows/headways, applied to an illustrative circuit.

    Football-day shutdowns and unscheduled service advisories need explicit
    future scenarios; this preset never claims to be a live timetable.
    """
    minute %= 1440
    if day_type == "closed" or not 420 <= minute < (1140 if day_type == "class_break" else 1320):
        return None
    if day_type == "weekend":
        return 1200
    if day_type == "class_break":
        return 900
    return 600 if minute < 1080 else 900
