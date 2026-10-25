"""Sanitize a bounded official OSM API JSON response; no network requests.

Usage: python build_expanded_snapshot.py /tmp/osu-expanded-osm.json
Raw contributor metadata and addresses are intentionally not persisted.
"""
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
BBOX = [-83.0183, 39.9940, -83.0003, 40.0045]
URL = "https://api.openstreetmap.org/api/0.6/map.json?bbox=" + ",".join(map(str, BBOX))
FOOD_AMENITIES = {"restaurant", "cafe", "fast_food", "food_court", "ice_cream"}
KEYS = set("access area bicycle bridge building building:levels building:use bus covered crossing crossing:signals cuisine drink:coffee cycleway entrance foot footway height highway incline kerb landuse lanes layer leisure level maxspeed motor_vehicle motorcar name natural oneway public_transport ramp ramp:wheelchair service sidewalk sidewalk:both step_count surface tactile_paving tunnel type vehicle water wheelchair amenity office club shop".split())


def selected(tags):
    return ("building" in tags or "highway" in tags or "entrance" in tags
            or tags.get("natural") in {"water","tree"} or tags.get("landuse") == "grass"
            or tags.get("amenity") in FOOD_AMENITIES
            or tags.get("leisure") == "park" or tags.get("public_transport") == "platform")


def inside(point, ring):
    x, y = point
    result = False
    for a, b in zip(ring, ring[1:]):
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            result = not result
    return result


def stitch(parts):
    parts = [list(p) for p in parts]
    rings = []
    while parts:
        line = parts.pop()
        while line[0] != line[-1]:
            for i, other in enumerate(parts):
                if line[-1] == other[0]:
                    line.extend(other[1:]); parts.pop(i); break
                if line[-1] == other[-1]:
                    line.extend(reversed(other[:-1])); parts.pop(i); break
                if line[0] == other[-1]:
                    line = other[:-1]+line; parts.pop(i); break
                if line[0] == other[0]:
                    line = list(reversed(other[1:]))+line; parts.pop(i); break
            else:
                return None
        rings.append(line)
    return rings


def main():
    raw_path = Path(sys.argv[1])
    raw = raw_path.read_bytes()
    source = json.loads(raw)
    nodes = {e["id"]: [e["lon"], e["lat"]] for e in source["elements"] if e["type"] == "node"}
    ways = {e["id"]: e for e in source["elements"] if e["type"] == "way"}
    features, issues, consumed = [], [], set()

    def add(element, geometry, extra=None):
        tags = {k: v for k, v in element.get("tags", {}).items() if k in KEYS}
        if "building" in tags and re.match(r"^\d+\s",tags.get("name","")):
            tags.pop("name")  # Address-form names are not needed for fictional households.
        tags.update(osm_type=element["type"], osm_id=element["id"])
        tags.update(extra or {})
        features.append({"type": "Feature", "id": f'{element["type"]}/{element["id"]}',
                         "properties": tags, "geometry": geometry})

    for element in source["elements"]:
        tags = element.get("tags", {})
        if element["type"] != "relation" or tags.get("type") != "multipolygon" or not selected(tags):
            continue
        parts = {"outer": [], "inner": []}
        member_ids = []
        for member in element.get("members", []):
            if member["type"] != "way" or member.get("role", "") not in {"", "outer", "inner"}:
                continue
            way = ways.get(member["ref"])
            if not way or not all(n in nodes for n in way["nodes"]):
                parts = None; break
            parts[member.get("role") or "outer"].append(way["nodes"])
            member_ids.append(member["ref"])
        stitched = {k: stitch(v) for k, v in parts.items()} if parts else None
        if not stitched or not stitched["outer"] or stitched["inner"] is None:
            issues.append(f'relation/{element["id"]}: incomplete members'); continue
        outers = [[nodes[n] for n in ring] for ring in stitched["outer"]]
        inners = [[nodes[n] for n in ring] for ring in stitched["inner"]]
        polygons = [[outer]+[inner for inner in inners if inside(inner[0], outer)] for outer in outers]
        add(element, {"type": "Polygon" if len(polygons) == 1 else "MultiPolygon",
                      "coordinates": polygons[0] if len(polygons) == 1 else polygons}, {"osm_member_way_ids": member_ids})
        consumed.update(member_ids)
    for element in source["elements"]:
        tags = element.get("tags", {})
        if not selected(tags):
            continue
        if element["type"] == "node":
            add(element, {"type": "Point", "coordinates": nodes[element["id"]]})
        elif element["type"] == "way" and element["id"] not in consumed:
            if not all(n in nodes for n in element["nodes"]):
                issues.append(f'way/{element["id"]}: missing nodes'); continue
            coords = [nodes[n] for n in element["nodes"]]
            polygon = len(coords) > 3 and coords[0] == coords[-1] and ("building" in tags or tags.get("area") == "yes" or tags.get("natural") == "water" or tags.get("landuse") == "grass" or tags.get("leisure") == "park")
            add(element, {"type": "Polygon" if polygon else "LineString", "coordinates": [coords] if polygon else coords}, {"osm_node_ids": element["nodes"]})
    collection = {"type": "FeatureCollection", "name": "OSU campus and University District", "selection_bbox": BBOX,
                  "attribution": "© OpenStreetMap contributors", "license": "https://opendatacommons.org/licenses/odbl/1-0/",
                  "source": URL, "features": sorted(features, key=lambda f: f["id"])}
    output = json.dumps(collection, separators=(",", ":"), ensure_ascii=False).encode()
    (ROOT / "osu-district.geojson").write_bytes(output)
    manifest = {"source_endpoint": URL, "retrieved_at_utc": datetime.fromtimestamp(raw_path.stat().st_mtime, timezone.utc).isoformat(),
                "converted_at_utc": datetime.now(timezone.utc).isoformat(),
                "selection_bbox_west_south_east_north": BBOX, "source_response_sha256": hashlib.sha256(raw).hexdigest(),
                "source_response_bytes": len(raw), "geojson_sha256": hashlib.sha256(output).hexdigest(),
                "geojson_bytes": len(output), "feature_count": len(features),
                "building_types": dict(Counter(f["properties"]["building"] for f in features if "building" in f["properties"])),
                "food_amenities": dict(Counter(f["properties"]["amenity"] for f in features if f["properties"].get("amenity") in FOOD_AMENITIES)),
                "assembly_issues": issues, "geometry_policy": "Complete selected ways; multipolygon holes preserved; incomplete relations omitted. Application clips scenery and excludes cut building destinations.",
                "privacy_filter": "Public map geometry and whitelisted circulation/building tags only; no addresses, contact details, contributor metadata, or occupants.",
                "attribution": "© OpenStreetMap contributors", "license": "ODbL 1.0"}
    (ROOT / "osu-district-manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
