"""Pinned OSU exterior geography with separate metric walking and driving graphs.

OSM is geographic evidence, not an assertion of current access, building opening
hours or emergency suitability. The small map uses a documented WGS84 local
tangent approximation. Authoring overlays never overwrite the geographic source.
"""
import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise
from pathlib import Path

import networkx as nx

from .world import uniform

WORLD_VERSION = "osu-campus-district/2.1"
CAMPUS_SIZE = 68
CAMPUS_BBOX = (-83.0183, 39.9940, -83.0003, 40.0045)
METERS_PER_UNIT = 24.25
DATA = Path(__file__).resolve().parents[1] / "data"
WALK_TYPES = {"footway", "pedestrian", "steps", "cycleway", "living_street"}
DRIVE_TYPES = {"primary", "secondary", "tertiary", "unclassified", "residential", "living_street", "service"}
RESTRICTED = {"no", "private", "customers", "delivery"}
MEAL_AMENITIES = {"restaurant", "fast_food", "food_court", "cafe"}
OFFICIAL_RESIDENCE_NAMES = {
    "Baker Hall", "Baker Hall East", "Baker Hall West", "Bradley Hall", "Canfield Hall",
    "Fechko House", "Fechko Alumnae Scholarship House", "German House", "Hanley House",
    "Mack Hall", "Morrison Tower", "Neil Building", "Park-Stradley Hall", "Paterson Hall",
    "Pennsylvania Place", "Pomerene House", "Scholars House East", "Scholars House West",
    "Siebert Hall", "Smith-Steeb Hall", "The Residence on Tenth", "Worthington Building",
}
RESIDENCE_SOURCE = "https://housing.osu.edu/hms/roomsearch?campus=1&view=map"


def _food_source(source_id, tags):
    cuisine = {value.strip() for value in tags.get("cuisine", "").split(";")}
    beverage_only = bool(cuisine & {"bubble_tea","tea","juice","smoothie"}) and not cuisine & {"coffee_shop","deli","breakfast","sandwich"}
    cafe = tags.get("amenity") == "cafe"
    return {"source_id":source_id,"name":tags.get("name"),"amenity":tags.get("amenity"),
            "cuisine":tags.get("cuisine"),"food_service":tags.get("amenity") in MEAL_AMENITIES and not (cafe and beverage_only),
            "coffee_service":cafe and tags.get("drink:coffee") != "no" and (not beverage_only or tags.get("drink:coffee") == "yes")}


def project(lonlat):
    """Stable metric world coordinates; enlarging the map never shrinks people."""
    west, south, _east, north = CAMPUS_BBOX
    latitude = math.radians((south+north)/2)
    eccentricity = (1/298.257223563)*(2-1/298.257223563)
    divisor = 1-eccentricity*math.sin(latitude)**2
    xm = math.pi/180*6378137/math.sqrt(divisor)*math.cos(latitude)
    ym = math.pi/180*6378137*(1-eccentricity)/divisor**1.5
    y0 = (CAMPUS_SIZE-(north-south)*ym/METERS_PER_UNIT)/2
    return (round(1+(lonlat[0]-west)*xm/METERS_PER_UNIT, 6),
            round(y0+(north-lonlat[1])*ym/METERS_PER_UNIT, 6))


CAMERA_FOCUS = list(project((-83.0123, 39.9994)))
DEFAULT_ORIGINS = {kind: [round(v) for v in project(lonlat)] for kind, lonlat in {
    "flood": (-83.0149, 39.9979), "wildfire": (-83.0158, 40.0011),
    "tornado": (-83.0170, 39.9970), "blizzard": (-83.0123, 39.9994),
    "hailstorm": (-83.0158, 40.0004), "thunderstorm": (-83.0161, 40.0004),
    "public_safety": (-83.0099, 39.9990),
}.items()}


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _clip_segment(a, b, bounds):
    """Liang–Barsky clipping; boundary nodes retain the segment's direction."""
    left, top, right, bottom = bounds
    dx, dy = b[0] - a[0], b[1] - a[1]
    low, high = 0.0, 1.0
    for p, q in ((-dx, a[0]-left), (dx, right-a[0]), (-dy, a[1]-top), (dy, bottom-a[1])):
        if p == 0:
            if q < 0:
                return None
        elif p < 0:
            low = max(low, q / p)
        else:
            high = min(high, q / p)
        if low > high:
            return None
    return (tuple(round(a[i] + low*(b[i]-a[i]), 6) for i in (0, 1)),
            tuple(round(a[i] + high*(b[i]-a[i]), 6) for i in (0, 1)))


def _clip_ring(ring, bounds):
    points = list(ring[:-1] if ring and ring[0] == ring[-1] else ring)
    for axis, edge, sign in ((0, bounds[0], 1), (0, bounds[2], -1),
                             (1, bounds[1], 1), (1, bounds[3], -1)):
        output = []
        if not points:
            return []
        previous = points[-1]
        for current in points:
            before, after = (previous[axis]-edge)*sign >= 0, (current[axis]-edge)*sign >= 0
            if before != after:
                frac = (edge-previous[axis])/(current[axis]-previous[axis])
                output.append(tuple(previous[i]+frac*(current[i]-previous[i]) for i in (0, 1)))
            if after:
                output.append(current)
            previous = current
        points = output
    return [list(p) for p in points + points[:1]] if len(points) >= 3 else []


def inside_polygon(point, ring):
    x, y = point
    inside = False
    for a, b in pairwise(ring):
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1]) + a[0]:
            inside = not inside
    return inside


def _nearest(point, a, b):
    length = (b[0]-a[0])**2+(b[1]-a[1])**2
    ratio = max(0, min(1, ((point[0]-a[0])*(b[0]-a[0])+(point[1]-a[1])*(b[1]-a[1]))/length)) if length else 0
    return tuple(round(a[i]+ratio*(b[i]-a[i]), 6) for i in (0,1))


def _closest_segments(a, b, c, d):
    candidates = [(a, _nearest(a,c,d)), (b, _nearest(b,c,d)),
                  (_nearest(c,a,b), c), (_nearest(d,a,b), d)]
    return min(candidates, key=lambda pair: distance(*pair))


def _cells(points, margin=0):
    left, right = min(p[0] for p in points)-margin, max(p[0] for p in points)+margin
    top, bottom = min(p[1] for p in points)-margin, max(p[1] for p in points)+margin
    return ((x,y) for x in range(math.floor(left/2),math.floor(right/2)+1)
            for y in range(math.floor(top/2),math.floor(bottom/2)+1))


def _wall_cuts(a, b, rings):
    cuts = [0.0,1.0]
    vx, vy = b[0]-a[0], b[1]-a[1]
    for ring in rings:
        for c,d in pairwise(ring):
            wx,wy = d[0]-c[0],d[1]-c[1]
            determinant = vx*wy-vy*wx
            if abs(determinant) < 1e-10:
                continue
            t = ((c[0]-a[0])*wy-(c[1]-a[1])*wx)/determinant
            u = ((c[0]-a[0])*vy-(c[1]-a[1])*vx)/determinant
            if 0 < t < 1 and 0 <= u <= 1:
                cuts.append(t)
    return sorted(set(cuts))


def _crosses_building(a, b, rings):
    """Test every interval cut by a wall, including thin intervening buildings."""
    vx,vy = b[0]-a[0],b[1]-a[1]
    for low,high in pairwise(_wall_cuts(a,b,rings)):
        if high-low < 1e-7:
            continue
        t = (low+high)/2
        p = (a[0]+t*vx,a[1]+t*vy)
        if inside_polygon(p,rings[0]) and not any(inside_polygon(p,hole) for hole in rings[1:]):
            return True
    return False


def _exterior_segments(a,b,rings,scale):
    """Retain outside portions up to the real footprint boundary, not interiors.

    Ten centimetres accommodates map rounding along a wall; it is not a usable
    passage width. Polygon holes remain exterior courtyard space.
    """
    segments = []
    for low,high in pairwise(_wall_cuts(a,b,rings)):
        midpoint = tuple(a[i]+(low+high)/2*(b[i]-a[i]) for i in (0,1))
        interior = inside_polygon(midpoint,rings[0]) and not any(inside_polygon(midpoint,h) for h in rings[1:])
        if interior and min(distance(midpoint,_nearest(midpoint,c,d)) for ring in rings for c,d in pairwise(ring))*scale > .1:
            continue
        start,end = (tuple(round(a[i]+t*(b[i]-a[i]),6) for i in (0,1)) for t in (low,high))
        if distance(start,end) > .000001:
            segments.append((start,end))
    return segments


@dataclass
class CampusCity:
    graph: nx.Graph
    vehicle_graph: nx.DiGraph
    places: list[dict]
    geometry: dict
    meters_per_unit: float
    map_bounds: list[float]
    source_hash: str
    parking: list[dict]
    layout: str = "campus"
    size: int = CAMPUS_SIZE
    portals: list[dict] | None = None

    @property
    def roads(self):
        return list(self.graph)

    @property
    def safe_zones(self):
        return []

    def serialize(self):
        return {
            "size": self.size, "layout": self.layout, "coordinate_space": "continuous",
            "camera_focus": CAMERA_FOCUS,
            "world_version": WORLD_VERSION, "meters_per_unit": self.meters_per_unit,
            "map_bounds": self.map_bounds, "roads": [list(p) for p in self.graph],
            "buildings": [], "river": [], "safe_zones": [], "places": self.places,
            "road_styles": [], "campus_geometry": self.geometry,
            "walk_edges": [[list(a), list(b)] for a, b in self.graph.edges],
            "vehicle_edges": [[list(a), list(b)] for a, b in self.vehicle_graph.edges],
            "parking": self.parking, "portals": self.portals or [],
            "neighborhoods": [{"name": name, "position": list(project(coords))} for name, coords in
                              (("The Oval", (-83.0123,39.9994)), ("Mirror Lake", (-83.0149,39.9979)),
                               ("High Street", (-83.0076,39.9994)), ("University District", (-83.0038,40.0011)),
                               ("South Campus", (-83.0105,39.9955)))],
            "default_origins": DEFAULT_ORIGINS,
            "geography_provenance": {
                "source": "OpenStreetMap", "attribution": "© OpenStreetMap contributors",
                "url": "https://www.openstreetmap.org/copyright", "license": "ODbL 1.0",
                "source_sha256": self.source_hash, "snapshot": "2026-10-25T02:25:09Z",
                "projection": "WGS84 local tangent approximation at -83.0093,39.99925; north up",
                "selection_bbox": list(CAMPUS_BBOX),
                "limitations": "Synthetic occupants and activities. Access tags are incomplete; no verified accessible or emergency routes. Traffic signals, turn restrictions and live closures are not modeled.",
            },
        }


@lru_cache(maxsize=1)
def make_campus_city():
    raw = (DATA / "osu-district.geojson").read_bytes()
    source = json.loads(raw)
    west, south, east, north = CAMPUS_BBOX
    scale, xy = METERS_PER_UNIT, project
    top_left, bottom_right = xy((west,north)), xy((east,south))
    bounds = [*top_left, *bottom_right]

    walk, drive = nx.Graph(), nx.DiGraph()
    geometry = {k: [] for k in ("buildings", "paths", "roads", "water", "greens", "trees")}
    building_sources = []
    food_points = []
    for feature in source["features"]:
        tags, geom = feature["properties"], feature["geometry"]
        kind = tags.get("highway")
        if geom["type"] == "Point" and tags.get("amenity") in MEAL_AMENITIES:
            point = xy(geom["coordinates"])
            if bounds[0] <= point[0] <= bounds[2] and bounds[1] <= point[1] <= bounds[3] and tags.get("access") not in {"no","private","delivery"}:
                food_points.append({**_food_source(feature["id"],tags),"position":point})
        elif geom["type"] == "Point" and tags.get("natural") == "tree":
            point = xy(geom["coordinates"])
            if bounds[0] <= point[0] <= bounds[2] and bounds[1] <= point[1] <= bounds[3]:
                geometry["trees"].append({"id":feature["id"],"kind":"tree","geometry":{"type":"Point","coordinates":list(point)}})
        elif geom["type"] == "LineString" and kind:
            coords = [xy(p) for p in geom["coordinates"]]
            foot_access = tags.get("foot", tags.get("access", "yes")) not in RESTRICTED
            car_access = tags.get("motorcar",tags.get("motor_vehicle", tags.get("vehicle", tags.get("access", "yes")))) not in RESTRICTED
            # Walkers use mapped pedestrian edges; streets are not automatically sidewalks.
            walkable = kind in WALK_TYPES and foot_access and tags.get("construction") is None
            driveable = kind in DRIVE_TYPES and car_access and tags.get("construction") is None
            for index, (start, end) in enumerate(pairwise(coords)):
                clipped = _clip_segment(start, end, bounds)
                if not clipped or distance(*clipped) < .00001:
                    continue
                start, end = clipped
                metadata = {"weight": distance(start, end)*scale, "source_id": feature["id"],
                            "kind": kind, "steps": kind == "steps", "accessibility": tags.get("wheelchair", "unknown"),
                            "width_m": 3.0 if kind != "steps" else 1.6}
                if walkable:
                    walk.add_edge(start, end, **metadata)
                if driveable:
                    one_way = tags.get("oneway")
                    if one_way != "-1":
                        drive.add_edge(start, end, **metadata)
                    if one_way not in {"yes", "1", "true"}:
                        drive.add_edge(end, start, **metadata)
                geometry["paths" if kind in WALK_TYPES else "roads"].append({
                    "id": f"{feature['id']}/{index}", "name": tags.get("name"), "kind": kind,
                    "restricted": not foot_access if kind in WALK_TYPES else not car_access,
                    "geometry": {"type": "LineString", "coordinates": [list(start), list(end)]},
                })
        elif geom["type"] in {"Polygon", "MultiPolygon"}:
            polygons = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
            bucket = ("water" if tags.get("natural") == "water" else "buildings" if "building" in tags
                      else "greens" if tags.get("landuse") == "grass" or tags.get("leisure") == "park"
                      else "paths" if kind in WALK_TYPES else None)
            if bucket is None:
                continue
            for index, polygon in enumerate(polygons):
                rings = [_clip_ring([xy(p) for p in ring], bounds) for ring in polygon]
                if not rings[0]:
                    continue
                entry = {"id": feature["id"] if index == 0 else f"{feature['id']}/{index}",
                         "name": tags.get("name"), "kind": tags.get("building") or kind or bucket,
                         "building_type": tags.get("building"),
                         "levels": tags.get("building:levels"),
                         "geometry": {"type": "Polygon", "coordinates": [ring for ring in rings if ring]}}
                geometry[bucket].append(entry)
                if bucket == "buildings":
                    # Cut footprints are scenery, never homes or interior destinations.
                    whole = all(west <= p[0] <= east and south <= p[1] <= north for p in polygon[0])
                    building_sources.append((entry, tags, whole))

    # An exterior-only scene cannot animate mapped interior corridors through a
    # solid roof. Trim those portions at footprint boundaries before connectivity
    # selection, preserving usable approach segments and courtyard holes.
    solid_grid = defaultdict(set)
    for index,(entry,tags,_) in enumerate(building_sources):
        if tags.get("building") in {"roof","roof;yes","bridge","no"}:
            continue
        for cell in _cells(entry["geometry"]["coordinates"][0]):
            solid_grid[cell].add(index)
    for a,b,metadata in list(walk.edges(data=True)):
        candidates = set().union(*(solid_grid[cell] for cell in _cells((a,b))))
        segments = [(a,b)]
        for index in candidates:
            rings = building_sources[index][0]["geometry"]["coordinates"]
            segments = [section for start,end in segments for section in _exterior_segments(start,end,rings,scale)]
            if not segments:
                break
        if segments != [(a,b)]:
            walk.remove_edge(a,b)
            for start,end in segments:
                walk.add_edge(start,end,**{**metadata,"weight":distance(start,end)*scale})
    # Use only the connected public pedestrian core; detached features remain scenery.
    walk = walk.subgraph(max(nx.connected_components(walk), key=len)).copy()
    # Strong connectivity provides valid outward and return car trips while preserving one-way edges.
    drive = drive.subgraph(max(nx.strongly_connected_components(drive), key=len)).copy()
    walk_nodes, drive_nodes = tuple(walk), tuple(drive)
    edge_grid, building_grid, splits = defaultdict(set), defaultdict(set), defaultdict(set)
    obstacles = [entry for entry,_,_ in building_sources]+geometry["water"]
    original_edges = list(walk.edges(data=True))
    for index,(a,b,_) in enumerate(original_edges):
        for cell in _cells((a,b)):
            edge_grid[cell].add(index)
    for index,entry in enumerate(obstacles):
        for cell in _cells(entry["geometry"]["coordinates"][0]):
            building_grid[cell].add(index)
    named_roads = [(tuple(f["geometry"]["coordinates"][0]),tuple(f["geometry"]["coordinates"][1]),f["name"])
                   for f in geometry["roads"] if f.get("name") and f["geometry"]["type"] == "LineString"]
    places = []
    for entry, tags, whole in building_sources:
        if not whole or tags.get("building") in {"construction", "roof", "roof;yes", "bridge", "service", "industrial", "garage", "garages", "shed", "no"}:
            continue
        ring = entry["geometry"]["coordinates"][0]
        # Connect the actual footprint boundary to a nearby mapped public path.
        # A spatial index avoids projecting every building against the whole city.
        indexes = set().union(*(edge_grid[cell] for cell in _cells(ring,1.5)))
        candidates = []
        for index in indexes:
            a,b,metadata = original_edges[index]
            path_point,door = min((_closest_segments(a,b,c,d) for c,d in pairwise(ring)),key=lambda pair: distance(*pair))
            gap = distance(path_point,door)*scale
            if gap > 32 or inside_polygon(path_point,ring) and gap > .01:
                continue
            if gap <= .01:
                door = path_point  # Coincident mapped doors; suppress rounding-size connectors.
            nearby = set().union(*(building_grid[cell] for cell in _cells((path_point,door))))
            if gap > .01 and any(_crosses_building(path_point,door,obstacles[i]["geometry"]["coordinates"]) for i in nearby):
                continue
            candidates.append((gap+(6 if metadata.get("steps") else 0),index,path_point,tuple(door)))
        if not candidates:
            continue
        _,edge_index,path_point,entrance = min(candidates)
        splits[edge_index].add(path_point)
        if path_point != entrance:
            walk.add_edge(path_point,entrance,weight=distance(path_point,entrance)*scale,kind="entrance_connector",
                          source_id=entry["id"],steps=False,width_m=1.4,accessibility="unknown",authored=True)
            geometry["paths"].append({"id": f'{entry["id"]}/entrance', "name": None,"kind":"entrance_connector",
                                      "geometry":{"type":"LineString","coordinates":[list(path_point),list(entrance)]}})
        osm_building_type = tags.get("building")
        name_lower = (entry["name"] or "").lower()
        student_house = bool(re.search(r"\b(alpha|beta|gamma|delta|epsilon|epilson|zeta|theta|kappa|lambda|sigma|omega|fraternity|sorority)\b",name_lower)) or name_lower == "evans scholars"
        official_dorm = entry["name"] in OFFICIAL_RESIDENCE_NAMES
        use_conflict = (tags.get("amenity") in {"place_of_worship","social_facility","school","university","community_centre"}
                        or tags.get("office") or tags.get("shop") or "student jewish center" in name_lower)
        unknown_named_house = bool(entry["name"] and osm_building_type in {"house","detached"} and not student_house and not official_dorm)
        building_type = ("house" if osm_building_type in {"house","detached","semidetached_house"}
                         else "apartments" if osm_building_type in {"apartments","residential","terrace"} else osm_building_type)
        if official_dorm:
            building_type = "dormitory"
        elif student_house:
            building_type = "apartments"
        housing_type = {"house":"house","apartments":"apartment","dormitory":"dormitory"}.get(building_type)
        if use_conflict or unknown_named_house:
            housing_type = None
        if student_house:
            housing_type = "student_house"
        entry["housing_type"] = housing_type
        street = min(named_roads,key=lambda road: distance(entrance,_nearest(entrance,*road[:2])))[2] if housing_type else None
        name = entry["name"] or (f"{street} house" if building_type == "house"
                                 else f"{street} apartments" if building_type == "apartments"
                                 else "Campus building")
        kind = ("home" if housing_type
                else "shop" if building_type in {"commercial","retail"}
                else "civic" if any(v in name for v in ("Library", "Union", "Pomerene"))
                else "school" if building_type == "university" else "work")
        if building_type == "parking":
            kind = "work"
        footprint_area = abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in pairwise(ring)))/2*scale**2
        try:
            levels = min(12,max(1,float(tags.get("building:levels",2))))
        except ValueError:
            levels = 2
        capacity = 6 if housing_type == "house" else max(4,min(120,int(footprint_area*levels/30))) if housing_type in {"apartment","student_house"} else 180
        place = {"id": entry["id"], "name": name.replace("William Oxley Thompson Memorial Library", "Thompson Library"),
                 "kind": kind, "position": [min(p[0] for p in ring), min(p[1] for p in ring)],
                 "footprint": ring, "polygon": ring, "footprint_type": "polygon", "entrance": list(entrance),
                 "facing": "s", "variant": int(uniform(42, "building", entry["id"])*4),
                 "solid_building": True, "building_type": building_type, "osm_building_type": osm_building_type,
                 "housing_type": housing_type, "street_name": street, "footprint_area_m2": round(footprint_area,1),
                 "housing_classification_source": RESIDENCE_SOURCE if official_dorm else "OSM building/use tags",
                 "family_home_eligible": housing_type == "house",
                 "household_capacity": 1 if housing_type == "house" else max(1,capacity//3) if housing_type in {"apartment","student_house"} else 90,
                 "capacity": capacity, "capacity_provenance": "authored scenario capacity; not measured occupancy",
                 "entrance_provenance": "footprint boundary connected to mapped path; short authored exterior connector where needed; not a verified real door",
                 "shelter_eligible": building_type != "parking",
                 "storm_shelter": building_type != "parking",
                 "public_shelter": kind in {"school","civic","shop"} and building_type != "parking" and tags.get("access") not in RESTRICTED,
                 "is_parking": building_type == "parking"}
        # A commercial footprint is not evidence of a restaurant. Retain explicit
        # food use, then attach POIs only when contained in this same building.
        eligible_service = kind != "home" and not place["is_parking"] and tags.get("access") not in {"no","private","delivery"}
        sources = []
        if eligible_service and tags.get("amenity") in MEAL_AMENITIES:
            sources.append(_food_source(entry["id"],tags))
        if eligible_service:
            rings = entry["geometry"]["coordinates"]
            sources.extend({key:value for key,value in poi.items() if key != "position"} for poi in food_points
                           if inside_polygon(poi["position"],rings[0]) and not any(inside_polygon(poi["position"],hole) for hole in rings[1:]))
        place.update(food_service=any(s["food_service"] for s in sources),coffee_service=any(s["coffee_service"] for s in sources),
                     food_venues=sorted({s["name"] for s in sources if s["food_service"] and s.get("name")}),
                     coffee_venues=sorted({s["name"] for s in sources if s["coffee_service"] and s.get("name")}),
                     service_sources=sources,
                     service_provenance="OSM food amenity on this building or a contained POI; no proximity or generic retail inference")
        places.append(place)

    # Split each source path once, preserving all doors attached along the edge.
    for index,points in splits.items():
        a,b,metadata = original_edges[index]
        walk.remove_edge(a,b)
        chain = sorted({a,b,*points},key=lambda p: distance(a,p))
        for start,end in pairwise(chain):
            walk.add_edge(start,end,**{**metadata,"weight":distance(start,end)*scale})
    walk_nodes = tuple(walk)

    # Outdoor gathering destinations lie on actual mapped paths, not across lawns.
    for label, lonlat in (("The Oval", (-83.0123, 39.9994)), ("Mirror Lake Walk", (-83.0149, 39.9979)),
                          ("South Oval", (-83.0116, 39.99765))):
        target = xy(lonlat)
        entrance = min(walk_nodes, key=lambda p: distance(p, target))
        x, y = entrance
        places.append({"id": label.lower().replace(" ", "-"), "name": label, "kind": "park",
                       "position": [x-.15, y-.15], "footprint": [[x-.15,y-.15],[x+.15,y-.15],[x+.15,y+.15],[x-.15,y+.15],[x-.15,y-.15]],
                       "entrance": list(entrance), "facing": "s", "variant": 0,
                       "solid_building": False, "capacity": 200, "capacity_provenance": "authored"})
    # Transfer points are shared walk/drive junctions or short explicit crosswalk connectors.
    parking = []
    for place in [p for p in places if p.get("is_parking")]:
        end = tuple(place["entrance"])
        car = min(drive_nodes, key=lambda p: distance(p, end))
        pedestrian = None
        for candidate in sorted(walk_nodes,key=lambda p: distance(p,car))[:20]:
            if distance(car,candidate)*scale > 28:
                break
            nearby = set().union(*(building_grid[cell] for cell in _cells((car,candidate))))
            if not any(_crosses_building(car,candidate,obstacles[i]["geometry"]["coordinates"]) for i in nearby):
                pedestrian = candidate
                break
        if pedestrian is None:
            continue
        if car != pedestrian:
            walk.add_edge(car, pedestrian, weight=distance(car, pedestrian)*scale,
                          kind="parking_connector", source_id=place["id"], width_m=3.0,
                          steps=False, accessibility="unknown", authored=True)
        parking.append({"id": f"parking-{len(parking)}", "name": place["name"],
                        "position": list(car), "capacity": 24, "capacity_provenance": "authored",
                        "transfer_provenance": "authored walking transfer to mapped road; wall and water checked; not a verified garage entrance",
                        "place_id": place["id"]})
    if len(parking) < 2:
        raise RuntimeError("Campus driving requires at least two connected parking transfers")
    if not any(p["kind"] == "home" for p in places):
        raise RuntimeError("Campus map needs connected home destinations")
    # Boundary homes represent people who commute from beyond this scene. They
    # are portals, never fictional buildings, shelters or recorded real homes.
    step_free = nx.Graph((a,b) for a,b,edge in walk.edges(data=True) if not edge.get("steps"))
    main_step_free = max(nx.connected_components(step_free),key=len)
    public_nodes = [node for node in walk_nodes if node in main_step_free]
    portals = []
    for identifier,name,coordinate in (
        ("north","North High Street",(-83.0088,north)),
        ("south","South High Street",(-83.0070,south)),
        ("east","University District east",(east,40.0000)),
        ("west","West campus",(west,39.9993)),
    ):
        target = xy(coordinate)
        entrance = min(public_nodes,key=lambda node: distance(node,target))
        x,y = entrance
        portal = {"id":f"commuter-{identifier}","name":f"Off-map home · {name}","kind":"home",
                  "housing_type":"commuter","building_type":"commuter_portal","is_portal":True,
                  "shelter_eligible":False,"storm_shelter":False,"public_shelter":False,
                  "solid_building":False,"entrance":list(entrance),"position":list(entrance),
                  "footprint":[[x,y],[x+.01,y],[x+.01,y+.01],[x,y+.01],[x,y]],
                  "capacity":1000,"household_capacity":1000,"capacity_provenance":"authored commuter source",
                  "entrance_provenance":"connected public walking entry near scene boundary",
                  "vehicle_position":list(min(drive_nodes,key=lambda node: distance(node,entrance)))}
        places.append(portal)
        portals.append({key:portal[key] for key in ("id","name","position","vehicle_position")})
    return CampusCity(walk, drive, places, geometry, scale, bounds, hashlib.sha256(raw).hexdigest(), parking,portals=portals)
