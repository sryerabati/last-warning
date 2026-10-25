"""Pin real OSM context roads/paths/trees, without duplicating the campus survey."""
import argparse
import gzip
import hashlib
import json
import math
from collections import Counter
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True, help='Saved Overpass JSON response')
parser.add_argument('--query', type=Path, required=True, help='Exact Overpass query text')
parser.add_argument('--endpoint', default='https://overpass.private.coffee/api/interpreter')
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'frontend/public/assets/geography'
OUTER = (-83.030, 39.986, -82.990, 40.014)
INNER = (-83.0183, 39.9940, -83.0003, 40.0045)
KINDS = {'residential', 'service', 'footway', 'path', 'pedestrian', 'cycleway'}
ENDPOINT = args.endpoint


def inside(point, bbox):
    return bbox[0] <= point[0] <= bbox[2] and bbox[1] <= point[1] <= bbox[3]


def coordinate(value):
    point = (float(value['lon']), float(value['lat']))
    if not all(math.isfinite(number) for number in point):
        raise ValueError('Nonfinite source coordinate')
    return point


def simplify(points, tolerance=0.000004):
    if len(points) <= 2:
        return points
    a, b = points[0], points[-1]
    dx, dy = b[0]-a[0], b[1]-a[1]
    square = dx*dx+dy*dy
    distances = []
    for p in points[1:-1]:
        t = max(0., min(1., ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/square)) if square else 0
        distances.append(math.hypot(p[0]-a[0]-t*dx, p[1]-a[1]-t*dy))
    maximum = max(distances)
    if maximum <= tolerance:
        return [a, b]
    split = distances.index(maximum)+1
    return simplify(points[:split+1], tolerance)[:-1]+simplify(points[split:], tolerance)


def clipped_parts(points):
    """Split source segments at box boundaries; never bridge the campus hole."""
    parts, current = [], []
    for a, b in pairwise(points):
        dx, dy = b[0]-a[0], b[1]-a[1]
        cuts = {0., 1.}
        for box in (OUTER, INNER):
            if dx:
                cuts.update(t for edge in (box[0], box[2]) if 0 < (t := (edge-a[0])/dx) < 1)
            if dy:
                cuts.update(t for edge in (box[1], box[3]) if 0 < (t := (edge-a[1])/dy) < 1)
        values = sorted(cuts)
        for left, right in pairwise(values):
            midpoint = (a[0]+dx*(left+right)/2, a[1]+dy*(left+right)/2)
            if not inside(midpoint, OUTER) or inside(midpoint, INNER):
                if len(current) >= 2:
                    parts.append(current)
                current = []
                continue
            start = (a[0]+dx*left, a[1]+dy*left)
            end = (a[0]+dx*right, a[1]+dy*right)
            if current and math.dist(current[-1], start) > 1e-9:
                if len(current) >= 2:
                    parts.append(current)
                current = []
            if not current:
                current = [start]
            if math.dist(current[-1], end) > 1e-12:
                current.append(end)
    if len(current) >= 2:
        parts.append(current)
    return parts


raw = args.source.read_bytes()
document = json.loads(raw)
if document.get('remark'):
    raise ValueError(f"Incomplete Overpass response: {document['remark']}")
features = []
source_counts, omitted = Counter(), Counter()
for element in sorted(document['elements'], key=lambda item: (item['type'], item['id'])):
    tags = element.get('tags', {})
    if element['type'] == 'node' and tags.get('natural') == 'tree':
        source_counts['tree_nodes'] += 1
        point = coordinate(element)
        if not inside(point, OUTER) or inside(point, INNER):
            omitted['tree_inside_campus_or_outside_outer'] += 1
            continue
        rounded_point = [round(v, 6) for v in point]
        if inside(rounded_point, INNER):
            omitted['tree_rounded_onto_campus_boundary'] += 1
            continue
        features.append({'type': 'Feature', 'id': f"node/{element['id']}",
                         'properties': {'layer': 'tree', 'class': 'tree', 'source': 'openstreetmap'},
                         'geometry': {'type': 'Point', 'coordinates': rounded_point}})
    elif element['type'] == 'way' and tags.get('highway') in KINDS:
        source_counts['highway_ways'] += 1
        if tags.get('area') == 'yes':
            omitted['highway_areas'] += 1
            continue
        geometry = element.get('geometry', [])
        if len(geometry) < 2 or any('lon' not in point or 'lat' not in point for point in geometry):
            omitted['incomplete_way_geometry'] += 1
            continue
        points = [coordinate(point) for point in geometry]
        # Simplify before final clipping so a chord can never bridge the hole.
        parts = clipped_parts(simplify(points))
        if not parts:
            omitted['way_inside_campus_or_outside_outer'] += 1
        for index, part in enumerate(parts):
            rounded = []
            for point in part:
                value = [round(v, 6) for v in point]
                if not rounded or rounded[-1] != value:
                    rounded.append(value)
            if len(rounded) < 2:
                omitted['collapsed_clipped_segment'] += 1
                continue
            kind = tags['highway']
            features.append({'type': 'Feature', 'id': f"way/{element['id']}/context/{index}",
                             'properties': {'layer': 'road' if kind in {'residential', 'service'} else 'path',
                                            'class': kind, 'source': 'openstreetmap'},
                             'geometry': {'type': 'LineString', 'coordinates': rounded}})

collection = {'type': 'FeatureCollection', 'name': 'Ohio State surrounding street, path and tree context',
              'bbox': list(OUTER), 'features': features}
encoded = (json.dumps(collection, separators=(',', ':'), ensure_ascii=False)+'\n').encode()
counts = Counter(feature['properties']['layer'] for feature in features)
classes = Counter(feature['properties']['class'] for feature in features)
assert counts['road'] and counts['path'] and counts['tree']
assert len({feature['id'] for feature in features}) == len(features)
for feature in features:
    geometry = feature['geometry']
    points = [geometry['coordinates']] if geometry['type'] == 'Point' else geometry['coordinates']
    assert all(inside(point, OUTER) for point in points)
    if geometry['type'] == 'Point':
        assert not inside(points[0], INNER)
    else:
        assert len(points) >= 2
        # Endpoint rounding at six decimals permits sub-decimeter edge error.
        inset = (INNER[0]+.000001, INNER[1]+.000001, INNER[2]-.000001, INNER[3]-.000001)
        assert all(not inside(((a[0]+b[0])/2, (a[1]+b[1])/2), inset) for a, b in pairwise(points))

OUT.mkdir(parents=True, exist_ok=True)
(OUT/'opening-local-network.geojson').write_bytes(encoded)
provenance = {
    'schema': 'last-warning-opening-local-network/1', 'asset': 'opening-local-network.geojson',
    'asset_sha256': hashlib.sha256(encoded).hexdigest(), 'asset_bytes': len(encoded),
    'gzip_bytes': len(gzip.compress(encoded, mtime=0)), 'feature_count': len(features),
    'layer_counts': dict(counts), 'class_counts': dict(classes),
    'retrieved_at_utc': datetime.fromtimestamp(args.source.stat().st_mtime, UTC).isoformat(),
    'source': {'endpoint': ENDPOINT, 'query': args.query.read_text().strip(),
               'timestamp_osm_base': document.get('osm3s', {}).get('timestamp_osm_base'),
               'response_sha256': hashlib.sha256(raw).hexdigest(), 'response_bytes': len(raw),
               'source_element_counts': dict(source_counts), 'license': 'ODbL 1.0',
               'license_url': 'https://www.openstreetmap.org/copyright', 'attribution': '© OpenStreetMap contributors'},
    'transforms': {'selection_bbox_west_south_east_north': list(OUTER),
                   'exclude_campus_bbox_west_south_east_north': list(INNER),
                   'geometry_policy': 'Lines clipped to outer bounds and split around the campus rectangle. No bridged gaps. Actual OSM tree nodes only. Highway area=yes polygons omitted rather than misread as centerlines.',
                   'simplification': 'Douglas-Peucker tolerance 0.000004 degrees before clipping; coordinates rounded to six decimals.',
                   'feature_ids': 'Stable source node/way ID; clipped way pieces use /context/<part index>.',
                   'omitted_counts': dict(omitted),
                   'privacy': 'Geometry, general road class, and public source IDs only; no addresses, residents, names, contributors or private tags.',
                   'scope': 'Opening-only geographic context, never routing, mobility, shelter or hazard evidence.'}}
(OUT/'opening-local-network.provenance.json').write_text(json.dumps(provenance, indent=2, ensure_ascii=False)+'\n')
print(json.dumps({key: provenance[key] for key in ('asset_bytes', 'gzip_bytes', 'feature_count', 'layer_counts', 'class_counts', 'asset_sha256')}))
