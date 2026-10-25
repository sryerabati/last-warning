"""Original fictional city; NetworkX handles its actual road connectivity."""
import hashlib
import json
from dataclasses import dataclass, field
from itertools import pairwise

import networkx as nx
import numpy as np

from ..schemas import ScenarioConfig
from .geometry import river_cells

SIZE = 40
STREETS = {3, 9, 15, 21, 27, 33, 37}
BRIDGES = {9, 27}
SAFE_ZONES = [(3, 3), (37, 37)]
STORM_SHELTERS = [*SAFE_ZONES, (9, 9), (9, 27), (15, 15), (27, 9), (27, 27), (33, 21)]


def uniform(seed: int, *keys) -> float:
    """Keyed common random numbers; warning-dependent control flow cannot consume RNG."""
    key = json.dumps([seed, *keys], separators=(",", ":")).encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big") / 2**64


@dataclass
class City:
    graph: nx.Graph
    elevation: np.ndarray
    roads: list[tuple[int, int]]
    buildings: list[tuple[int, int]]
    river: list[tuple[int, int]]
    safe_zones: list[tuple[int, int]]
    places: list[dict] = field(default_factory=list)
    road_styles: list[dict] = field(default_factory=list)
    layout: str = "grid"

    def serialize(self):
        value = {
            "size": SIZE, "roads": self.roads, "buildings": self.buildings,
            "river": self.river, "safe_zones": self.safe_zones,
            "neighborhoods": [{"name": "North District", "position": [6, 5]},
                              {"name": "East Bank", "position": [30, 17]},
                              {"name": "Old Town", "position": [7, 30]}],
        }
        if self.layout == "organic":
            value.update(layout=self.layout, world_version="riverside-organic/1", places=self.places,
                         road_styles=self.road_styles,
                         default_origins={"flood": [19, 4], "wildfire": [6, 12], "tornado": [3, 35]})
        return value


def make_city(config: ScenarioConfig) -> City:
    if config.layout == "organic":
        return make_organic_city(config)
    graph = nx.Graph()
    river = [(x, y) for y in range(SIZE) for x in range(18, 21)]
    water = set(river)
    roads = [(x, y) for y in range(SIZE) for x in range(SIZE)
             if (x in STREETS or y in STREETS) and ((x, y) not in water or y in BRIDGES)]
    graph.add_nodes_from(roads)
    for x, y in roads:
        for neighbor in [(x + 1, y), (x, y + 1)]:
            if neighbor in graph:
                graph.add_edge((x, y), neighbor, weight=1)
    elevation = np.zeros((SIZE, SIZE))
    buildings = []
    for y in range(SIZE):
        for x in range(SIZE):
            elevation[y, x] = (abs(x - 19) * 0.105 + y * 0.012
                                + uniform(config.seed, "terrain", x, y) * 0.22)
            if (x, y) in water:
                elevation[y, x] = -0.5
            elif (x, y) not in graph and 0 < x < 39 and 0 < y < 39:
                buildings.append((x, y))
    for x, y in SAFE_ZONES:
        elevation[y, x] = 5
    safe_zones = STORM_SHELTERS if config.disaster_type == "tornado" else SAFE_ZONES
    return City(graph, elevation, roads, buildings, river, list(safe_zones))


def _line(start, end):
    """Rasterize a control segment as cardinal graph edges, never diagonals."""
    x, y = start
    yield x, y
    dx, dy = end[0] - x, end[1] - y
    count = abs(dx) + abs(dy)
    for step in range(count):
        # Spread stair steps along a sloping lane instead of an invented curve.
        next_x = round((step + 1) * abs(dx) / count) if count else 0
        old_x = round(step * abs(dx) / count) if count else 0
        if next_x > old_x:
            x += 1 if dx > 0 else -1
        else:
            y += 1 if dy > 0 else -1
        yield x, y


def make_organic_city(config):
    water = river_cells("organic")
    road_set = set()
    bridges = set()
    major_roads = set()

    def lane(points, bridge=False, major=False):
        for start, end in pairwise(points):
            for point in _line(start, end):
                if point not in water or bridge:
                    road_set.add(point)
                    if major:
                        major_roads.add(point)
                    if point in water:
                        bridges.add(point)

    # One canonical town, independent of resident seed, warning and disaster.
    lane([(3, 0), (3, 3), (5, 8), (2, 18), (4, 29), (3, 37), (3, 39)])
    lane([(7, 0), (8, 10), (6, 19), (10, 29), (8, 39)])
    lane([(12, 0), (11, 14), (12, 25), (11, 39)], major=True)
    lane([(26, 0), (27, 12), (25, 24), (27, 39)], major=True)
    lane([(32, 0), (30, 11), (33, 22), (30, 32), (32, 39)])
    lane([(37, 0), (35, 7), (38, 17), (36, 28), (37, 37), (37, 39)])
    for y in (4, 12, 21, 32, 37):
        lane([(1, y), (7, y), (12, y + (1 if y < 37 else -1))])
    for y in (3, 16, 25, 35, 37):
        lane([(25, y), (31, y + (1 if y < 37 else -1)), (39, y)])
    for y in (9, 27):
        lane([(3, y), (37, y)], bridge=True, major=True)
    for refuge in STORM_SHELTERS:
        nearest = min(road_set, key=lambda p: (abs(p[0]-refuge[0])+abs(p[1]-refuge[1]), p))
        lane([refuge, nearest])
    graph = nx.Graph()
    graph.add_nodes_from(sorted(road_set))
    for x, y in road_set:
        for other in ((x+1, y), (x, y+1)):
            if other in road_set:
                graph.add_edge((x, y), other, weight=1)
    if not nx.is_connected(graph):
        raise RuntimeError("The canonical town road network must stay connected")
    # A refuge is a real building beside its designated door, not an abstract
    # four-way junction. Turn one redundant intersection arm into its small lot.
    for x, y in STORM_SHELTERS:
        adjacent = [(x-1, y), (x+1, y), (x, y-1), (x, y+1)]
        if all(p in road_set or p in water for p in adjacent):
            for point in adjacent:
                if point in water or point in STORM_SHELTERS:
                    continue
                candidate = graph.copy()
                candidate.remove_node(point)
                if nx.is_connected(candidate):
                    graph = candidate
                    road_set.remove(point)
                    major_roads.discard(point)
                    bridges.discard(point)
                    break
    occupied = set()
    places = []

    def add_place(kind, name, size=(2, 2), near=None, entrance_required=None):
        candidates = []
        for y in range(1, 39-size[1]+1):
            for x in range(1, 39-size[0]+1):
                footprint = {(x+dx, y+dy) for dx in range(size[0]) for dy in range(size[1])}
                if footprint.intersection(water | road_set | occupied):
                    continue
                perimeter = ([((x-1, y+dy), "w") for dy in range(size[1])]
                             + [((x+size[0], y+dy), "e") for dy in range(size[1])]
                             + [((x+dx, y-1), "n") for dx in range(size[0])]
                             + [((x+dx, y+size[1]), "s") for dx in range(size[0])])
                doors = [(p, side) for p, side in perimeter
                         if p in road_set and (entrance_required is None or p == entrance_required)]
                if doors:
                    score = (abs(x-near[0])+abs(y-near[1])) if near else uniform(142, "place", x, y)
                    candidates.append((score, y, x, footprint, doors))
        if not candidates:
            return None
        _, y, x, footprint, doors = min(candidates, key=lambda c: c[:3])
        entrance, facing = min(doors)
        key = f"{kind}-{sum(p['kind'] == kind for p in places)+1:02d}"
        value = {"id": key, "name": name, "kind": kind, "position": [x, y],
                 "footprint": [list(p) for p in sorted(footprint)], "entrance": list(entrance),
                 "facing": facing, "variant": int(uniform(142, key) * 4)}
        places.append(value)
        occupied.update(footprint)
        return value

    for index, refuge in enumerate(STORM_SHELTERS):
        if (add_place("shelter", f"Refuge {index+1}", near=refuge, entrance_required=refuge) is None
                and add_place("shelter", f"Refuge {index+1}", size=(1, 1), near=refuge,
                              entrance_required=refuge) is None):
            raise RuntimeError("Every designated refuge needs a real accessible building")
    for index, near in enumerate([(7, 5), (31, 8), (8, 27), (32, 30)]):
        add_place("work", ["West workshop", "East offices", "Willow farm", "Orchard mill"][index],
                  size=(3, 3), near=near)
    for index, near in enumerate([(7, 17), (31, 20)]):
        add_place("school", ["West learning center", "East learning center"][index], size=(3, 3), near=near)
    for index, near in enumerate([(10, 9), (28, 27)]):
        add_place("civic", ["Town library", "Neighborhood hall"][index], size=(3, 3), near=near)
    for kind, names, points in [
        ("shop", ["West market", "East market", "South market"], [(7, 12), (30, 16), (9, 32)]),
        ("park", ["Willow green", "River garden", "East commons"], [(7, 21), (11, 5), (31, 35)]),
    ]:
        for name, near in zip(names, points, strict=True):
            add_place(kind, name, size=(3, 3), near=near)
    for index in range(64):
        if add_place("home", f"{index+1} {['Willow Lane', 'Orchard Walk', 'Mill Lane', 'River Close'][index % 4]}") is None:
            break
    for place in places:
        if place["kind"] in {"shop", "park"}:
            nearby = nx.single_source_shortest_path_length(graph, tuple(place["entrance"]), cutoff=2)
            place["activity_spots"] = [list(p) for p in sorted(nearby) if p not in water]
    elevation = np.zeros((SIZE, SIZE))
    for y in range(SIZE):
        center = sum(x for x, row in water if row == y) / 3
        for x in range(SIZE):
            elevation[y, x] = (-.5 if (x, y) in water else
                abs(x-center)*.105 + y*.012 + uniform(config.seed, "terrain", x, y)*.22)
    safe_zones = STORM_SHELTERS if config.disaster_type == "tornado" else SAFE_ZONES
    for x, y in safe_zones:
        elevation[y, x] = 5
    styles = [{"position": list(p), "kind": "bridge" if p in bridges else "road" if p in major_roads else "path"}
              for p in sorted(road_set)]
    buildings = [tuple(p) for place in places if place["kind"] != "park" for p in place["footprint"]]
    return City(graph, elevation, sorted(road_set), buildings, sorted(water), list(safe_zones), places, styles, "organic")
