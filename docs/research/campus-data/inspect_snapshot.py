"""Offline, research-only diagnostics and map; never fetches network data."""
from collections import Counter
from html import escape
import json
import math
from pathlib import Path

root = Path(__file__).parent
collection = json.loads((root / 'osu-core.geojson').read_text())
manifest = json.loads((root / 'manifest.json').read_text())
features = collection['features']
west, south, east, north = manifest['selection_bbox_west_south_east_north']
lon0, lat0 = (west + east) / 2, (south + north) / 2
a, flattening = 6378137.0, 1 / 298.257223563
e2 = flattening * (2 - flattening)
phi = math.radians(lat0)
prime_vertical = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
meridian = a * (1 - e2) / (1 - e2 * math.sin(phi) ** 2) ** 1.5
x_per_degree = math.pi / 180 * prime_vertical * math.cos(phi)
y_per_degree = math.pi / 180 * meridian
width_m, height_m = (east - west) * x_per_degree, (north - south) * y_per_degree
map_x, map_y, map_w = 40, 156, 1120
px_per_m = map_w / width_m
map_h = height_m * px_per_m

def xy(point):
    return ((point[0] - west) * x_per_degree * px_per_m + map_x,
            (north - point[1]) * y_per_degree * px_per_m + map_y)

def points(value):
    if value and isinstance(value[0], (float, int)):
        yield value
    else:
        for child in value:
            yield from points(child)

def path(geometry):
    kind, coords = geometry['type'], geometry['coordinates']
    if kind == 'Polygon':
        lines = coords
    elif kind == 'MultiPolygon':
        lines = [ring for polygon in coords for ring in polygon]
    else:
        lines = [coords]
    return ' '.join('M ' + ' L '.join(f'{x:.2f},{y:.2f}' for x, y in map(xy, line)) + (' Z' if kind in ('Polygon','MultiPolygon') else '') for line in lines)

roads, walks, steps, buildings, water, green = [], [], [], [], [], []
for feature in features:
    p, g = feature['properties'], feature['geometry']
    if g['type'] == 'Point':
        continue
    d = path(g)
    if p.get('natural') == 'water':
        water.append(f'<path d="{d}" fill="#8bbdce" stroke="#38798e" stroke-width="1.4" fill-rule="evenodd"/>')
    elif 'building' in p:
        buildings.append(f'<path d="{d}" fill="#aeb9bf" stroke="#596970" stroke-width="0.8" fill-rule="evenodd"/>')
    elif p.get('leisure') == 'park' or p.get('landuse') == 'grass':
        green.append(f'<path d="{d}" fill="#d9e6ca" fill-rule="evenodd"/>')
    elif 'highway' in p:
        kind = p['highway']
        if kind == 'steps':
            steps.append(f'<path d="{d}" fill="none" stroke="#b84d42" stroke-width="2" stroke-dasharray="2 2"/>')
        elif kind in ('footway','pedestrian','cycleway'):
            fill = '#e9d9bd' if g['type'] == 'Polygon' else 'none'
            walks.append(f'<path d="{d}" fill="{fill}" stroke="#b68642" stroke-width="1.35" fill-rule="evenodd"/>')
        else:
            weight = 9 if kind == 'primary' else 6 if kind in ('unclassified','residential','tertiary','living_street') else 3
            roads.append(f'<path d="{d}" fill="none" stroke="#747d80" stroke-width="{weight+1.5}" stroke-linejoin="round"/><path d="{d}" fill="none" stroke="#e1e4e2" stroke-width="{weight}" stroke-linejoin="round"/>')

# Basic shared-node connectivity is diagnostic only: no access, turn, crossing,
# slope, or safe-passage decision is implied by membership in one component.
parent = {}
def find(v):
    parent.setdefault(v,v)
    while parent[v] != v:
        parent[v] = parent[parent[v]]
        v = parent[v]
    return v
def union(a,b):
    pa,pb = find(a),find(b)
    if pa != pb:
        parent[pa] = pb
linear = [f for f in features if 'highway' in f['properties'] and f['geometry']['type'] == 'LineString']
edge_count = 0
for f in linear:
    nodes = f['properties'].get('osm_node_ids',[])
    for a,b in zip(nodes,nodes[1:]):
        union(a,b)
        edge_count += 1
components = Counter(find(v) for v in parent)
entrances = [f for f in features if f['geometry']['type']=='Point' and 'entrance' in f['properties']]
anchors = [f for f in features if f['properties'].get('name') in ('The Oval','William Oxley Thompson Memorial Library','Mirror Lake','Ohio Union','Pomerene Hall')]
coordinate_errors = []
ring_errors = []
for f in features:
    for p in points(f['geometry']['coordinates']):
        if len(p)!=2 or not all(math.isfinite(v) for v in p) or not -180<=p[0]<=180 or not -90<=p[1]<=90:
            coordinate_errors.append(f['id'])
    g = f['geometry']
    rings = g['coordinates'] if g['type']=='Polygon' else [r for p in g['coordinates'] for r in p] if g['type']=='MultiPolygon' else []
    for ring in rings:
        if len(ring)<4 or ring[0] != ring[-1]:
            ring_errors.append(f['id'])
diagnostics = {
    'feature_ids_unique':len({f['id'] for f in features})==len(features),
    'coordinate_errors':coordinate_errors,'unclosed_or_short_polygon_rings':ring_errors,
    'validation_scope':'Basic coordinate/closure checks only; no robust self-intersection, overlap, access, or routability validation performed.',
    'linear_highway_features':len(linear),'linear_highway_node_count':len(parent),
    'linear_highway_segment_occurrences':edge_count,
    'shared_node_component_count_ignoring_access':len(components),
    'largest_shared_node_component_sizes':sorted(components.values(),reverse=True)[:10],
    'mapped_entrance_point_count':len(entrances),
    'entrance_points_sharing_node_id_with_linear_highway':sum(f['properties']['osm_id'] in parent for f in entrances),
    'named_anchor_ids':{f['properties']['name']:f['id'] for f in anchors},
    'projection_for_visualization':{'method':'Local equirectangular tangent approximation using WGS84 prime-vertical and meridional radii at origin; north up; scale approximate','origin_lon_lat':[lon0,lat0],'x_metres_per_longitude_degree':x_per_degree,'y_metres_per_latitude_degree':y_per_degree,'extent_width_m':width_m,'extent_height_m':height_m},
}
(root/'diagnostics.json').write_text(json.dumps(diagnostics,indent=2)+'\n')

svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {map_y+map_h+130:.0f}" role="img" aria-label="Research map of Ohio State academic core from public OpenStreetMap geometry">',
       '<rect width="100%" height="100%" fill="#f7f7f2"/>',
       '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#26383e}.label{font-weight:700;font-size:15px;paint-order:stroke;stroke:#f7f7f2;stroke-width:4px;stroke-linejoin:round}</style>',
       '<text x="40" y="42" font-size="27" font-weight="700">Ohio State academic core · geometry feasibility</text>',
       '<text x="40" y="69" font-size="14">Actual OSM geometry · research artifact · no game styling or routing claims</text>',
       f'<text x="40" y="94" font-size="12">W {west:.4f}°   S {south:.4f}°   E {east:.4f}°   N {north:.4f}° · selected area ≈ {width_m:.0f} × {height_m:.0f} m</text>',
       f'<defs><clipPath id="extent"><rect x="{map_x}" y="{map_y}" width="{map_w}" height="{map_h}"/></clipPath></defs>',
       f'<rect x="{map_x}" y="{map_y}" width="{map_w}" height="{map_h}" fill="#edf0e8" stroke="#bdc7c2"/>']
legend = [('Roads','#747d80'),('Footpaths / pedestrian areas','#b68642'),('Steps','#b84d42'),('Buildings','#aeb9bf'),('Water','#8bbdce')]
for x,(name,color) in zip([40,210,490,640,820],legend):
    svg.append(f'<rect x="{x}" y="115" width="18" height="10" fill="{color}"/><text x="{x+26}" y="125" font-size="13">{name}</text>')
svg.append('<g clip-path="url(#extent)">')
svg.extend(green+water+roads+walks+steps+buildings)
label_specs = {
    'The Oval':('The Oval',0,-4),
    'William Oxley Thompson Memorial Library':('Thompson Library',-15,-28),
    'Mirror Lake':('Mirror Lake',-45,-12),
    'Ohio Union':('Ohio Union',0,0),
    'Pomerene Hall':('Pomerene Hall',-20,40),
}
for f in anchors:
    all_points = list(points(f['geometry']['coordinates']))
    p = [sum(c[0] for c in all_points)/len(all_points),sum(c[1] for c in all_points)/len(all_points)]
    x,y = xy(p); label,dx,dy = label_specs[f['properties']['name']]
    svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="#213a43"/><text class="label" x="{x+dx:.2f}" y="{y+dy:.2f}" text-anchor="middle">{escape(label)}</text>')
for road_name,target_lat in [('College Road',40.0005),('North High Street',39.9990)]:
    candidates = [f for f in linear if f['properties'].get('name')==road_name]
    candidates = [c for f in candidates for c in f['geometry']['coordinates'] if west<c[0]<east and south<c[1]<north]
    if candidates:
        p = min(candidates,key=lambda p:abs(p[1]-target_lat)); x,y=xy(p)
        svg.append(f'<text class="label" x="{x+15:.2f}" y="{y:.2f}" transform="rotate(-90 {x+15:.2f} {y:.2f})" text-anchor="middle">{escape(road_name)}</text>')
svg.append('</g>')
svg.extend(['<path d="M 1124 221 L 1136 251 L 1124 245 L 1112 251 Z" fill="#26383e"/>','<text x="1124" y="210" text-anchor="middle" font-size="17" font-weight="700">N</text>'])
bar_y=map_y+map_h+28; bar_x=40; bar_w=100*px_per_m
svg.extend([f'<path d="M {bar_x} {bar_y-5} V {bar_y+5} M {bar_x} {bar_y} H {bar_x+bar_w} M {bar_x+bar_w} {bar_y-5} V {bar_y+5}" stroke="#26383e" stroke-width="2"/>',
            f'<text x="{bar_x+bar_w/2}" y="{bar_y+23}" text-anchor="middle" font-size="12">≈ 100 m</text>',
            f'<text x="250" y="{bar_y+4}" font-size="12">North up · local WGS84 tangent approximation · displayed at selection extent</text>',
            f'<text x="40" y="{bar_y+57}" font-size="12">© OpenStreetMap contributors · ODbL 1.0 · openstreetmap.org/copyright · data {manifest["source_osm_timestamp"]}</text>',
            f'<text x="40" y="{bar_y+80}" font-size="12">Steps and incomplete accessibility tags require review. Raw split ways are not automatically valid route topology.</text>',
            '</svg>'])
(root/'osu-core-research.svg').write_text('\n'.join(svg)+'\n')
print(json.dumps(diagnostics,indent=2))
