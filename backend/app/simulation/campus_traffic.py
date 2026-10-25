"""Deterministic authored crossing coordination on the actual metric graphs.

Zones are geometric conflicts, not verified marked crosswalks or real signals.
The controller reserves a crossing until its occupant clears it; oldest arrival
wins, with pedestrians first on a simultaneous request. Lane following uses a
standstill gap plus reaction headway. No crash probability is inferred here.
"""
import math
from collections import defaultdict
from itertools import pairwise

ROAD_TYPES = {"primary", "secondary", "tertiary", "unclassified", "residential", "service", "living_street"}


def length(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])


def crossing(a, b, c, d):
    vx, vy = b[0]-a[0], b[1]-a[1]
    wx, wy = d[0]-c[0], d[1]-c[1]
    denominator = vx*wy-vy*wx
    if abs(denominator) < 1e-10:
        return None
    t = ((c[0]-a[0])*wy-(c[1]-a[1])*wx)/denominator
    u = ((c[0]-a[0])*vy-(c[1]-a[1])*vx)/denominator
    if -1e-8 <= t <= 1+1e-8 and -1e-8 <= u <= 1+1e-8:
        return a[0]+t*vx, a[1]+t*vy
    return None


class TrafficGeometry:
    def __init__(self, city):
        self.scale = city.meters_per_unit
        self.cell = 40/self.scale
        self.points = []
        self.grid = defaultdict(list)
        road_grid = defaultdict(list)
        roads = []
        seen = set()
        for a, b in city.vehicle_graph.edges:
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            index = len(roads)
            roads.append((a, b))
            for cell in self.cells(a, b):
                road_grid[cell].append(index)
        # Actual graph intersections, including shared nodes and crossing
        # segment interiors. Parallel roadside paths are not a crossing.
        for a, b, data in city.graph.edges(data=True):
            if data.get("kind") in ROAD_TYPES:
                continue
            nearby = {index for cell in self.cells(a, b) for index in road_grid[cell]}
            for index in sorted(nearby):
                point = crossing(a, b, *roads[index])
                if point is not None:
                    self.add(point)
        # Car-to-car intersection conflicts are shared road junctions, not
        # every polyline vertex on an otherwise straight road.
        for point in city.vehicle_graph:
            neighbors = set(city.vehicle_graph.successors(point)) | set(city.vehicle_graph.predecessors(point))
            if len(neighbors) >= 3:
                self.add(point)

    def cells(self, a, b, margin=0):
        return ((x, y) for x in range(math.floor((min(a[0], b[0])-margin)/self.cell), math.floor((max(a[0], b[0])+margin)/self.cell)+1)
                for y in range(math.floor((min(a[1], b[1])-margin)/self.cell), math.floor((max(a[1], b[1])+margin)/self.cell)+1))

    def add(self, point):
        # Closely spaced source vertices describe one conflict, avoiding
        # overlapping locks that can deadlock a turn through an intersection.
        for cell in self.cells(point, point, 8/self.scale):
            for index in self.grid[cell]:
                if length(point, self.points[index])*self.scale < 8:
                    return
        index = len(self.points)
        self.points.append(tuple(point))
        self.grid[next(self.cells(point, point))].append(index)

    def along(self, position, route, driving, limit=45):
        """First conflict in forward route distance, including current occupancy."""
        radius = (7.0 if driving else 5.2)/self.scale
        traveled = 0.0
        best = None
        for a, b in pairwise([position, *route]):
            segment = length(a, b)
            if segment < 1e-9:
                continue
            dx, dy = (b[0]-a[0])/segment, (b[1]-a[1])/segment
            candidates = {index for cell in self.cells(a, b, radius) for index in self.grid[cell]}
            for index in candidates:
                point = self.points[index]
                projection = (point[0]-a[0])*dx+(point[1]-a[1])*dy
                perpendicular2 = (point[0]-a[0])**2+(point[1]-a[1])**2-projection**2
                if perpendicular2 > radius**2:
                    continue
                half = math.sqrt(max(0, radius**2-perpendicular2))
                enter, leave = projection-half, projection+half
                if leave < -.001 or enter > segment:
                    continue
                distance = (traveled+max(0, enter))*self.scale
                if distance <= limit and (best is None or (distance, index) < best):
                    best = distance, index
            traveled += segment
            if traveled*self.scale > limit:
                break
        return best


class CampusTraffic:
    def __init__(self, city):
        if not hasattr(city, "_traffic_geometry"):
            city._traffic_geometry = TrafficGeometry(city)
        self.geometry = city._traffic_geometry
        self.scale = city.meters_per_unit
        self.leases = {}
        self.waiting_since = {}
        self.movers = {}
        self.vehicle_grid = defaultdict(list)
        self.mover_grid = defaultdict(list)
        self.now = 0.0
        self.dt = 1.0
        self.wait_events = 0
        self.active = False

    @staticmethod
    def key(unit):
        return str(unit.get("traffic_id", f"resident-{unit.get('id', unit.get('vehicle_id'))}"))

    def begin(self, units, vehicles, now, dt, speed_factor=1, headway_seconds=1.2, traction=1.):
        self.now, self.dt = now, dt
        self.headway_seconds, self.traction = headway_seconds, traction
        self.movers = {}
        self.vehicle_grid.clear()
        self.mover_grid.clear()
        claims = defaultdict(list)
        self.active = any(u["stage"] == "driving" or vehicles.get(u.get("vehicle_id"), {}).get("occupant_ids") for u in units)
        if not self.active:
            self.leases.clear()
            self.waiting_since.clear()
            return
        for unit in units:
            if unit["stage"] in {"boarding_bus", "alighting_bus"}:
                # A stopped bus holds its curb-transfer conflicts until boarding
                # and alighting finish; its passengers do not deadlock against
                # the very bus whose door they are approaching.
                bus_key = unit.get("transit", {}).get("bus_id")
                speed = unit.get("_traffic_speed", unit["speed"]*speed_factor)
                candidate = self.geometry.along(unit["position"], unit["route"], False, speed*dt+12)
                if bus_key and candidate:
                    distance, zone = candidate
                    since = self.waiting_since.setdefault((zone, bus_key), round(now+distance/max(.1, speed), 6))
                    claims[zone].append((since, 0, bus_key))
                continue
            if unit["stage"] == "riding_bus":
                continue  # Physical bus is indexed once, not once per passenger unit.
            key = self.key(unit)
            driving = unit["stage"] == "driving" or bool(vehicles.get(unit.get("vehicle_id"), {}).get("occupant_ids")) or vehicles.get(unit.get("vehicle_id"), {}).get("type") == "bus"
            moving = unit["stage"] in {"driving", "walking", "walk_to_car", "walk_to_bus"}
            if not moving and not driving:
                continue
            speed = unit.get("_traffic_speed", (6.0 if driving else unit["speed"])*speed_factor)
            self.movers[key] = (unit, driving, speed)
            self.mover_grid[next(self.geometry.cells(unit["position"], unit["position"]))].append(key)
            end = next((p for p in unit["route"] if length(p, unit["position"]) > 1e-8), None)
            if end:
                unit["heading"] = math.atan2(end[1]-unit["position"][1], end[0]-unit["position"][0])
            if driving:
                point = unit["position"]
                self.vehicle_grid[next(self.geometry.cells(point, point))].append(key)
            if unit.get("held") or unit.get("impact_until", 0) > now:
                continue
            candidate = self.geometry.along(unit["position"], unit["route"], driving, speed*dt+12)
            if candidate:
                distance, zone = candidate
                since = self.waiting_since.setdefault((zone, key), round(now+distance/max(.1, speed), 6))
                claims[zone].append((since, 1 if driving else 0, key))
        # Release only after the body/rear of the occupying unit has cleared.
        for zone, lease in list(self.leases.items()):
            key, expires = lease
            mover = self.movers.get(key)
            if mover is None:
                del self.leases[zone]
                continue
            unit, driving, speed = mover
            radius = 7 if driving else 5.2
            inside = length(unit["position"], self.geometry.points[zone])*self.scale <= radius+.1
            still_approaching = any(row[2] == key for row in claims[zone])
            if not inside and (not still_approaching or now >= expires):
                del self.leases[zone]
        for zone, candidates in sorted(claims.items()):
            if candidates and zone not in self.leases:
                _, _, key = min(candidates)
                unit, driving, speed = self.movers[key]
                # An already occupying unit must clear before new entrants.
                nearby = {other_key for cell in self.geometry.cells(self.geometry.points[zone], self.geometry.points[zone], 8/self.scale) for other_key in self.mover_grid[cell]}
                occupied = [(other_key, self.movers[other_key]) for other_key in nearby
                            if length(self.movers[other_key][0]["position"], self.geometry.points[zone])*self.scale < (7 if self.movers[other_key][1] else 5.2)]
                if occupied:
                    key, (_, driving, speed) = min(occupied, key=lambda row: row[0])
                self.leases[zone] = key, now+max(10, 30/max(.3, speed))
        active = {(zone, row[2]) for zone, rows in claims.items() for row in rows}
        self.waiting_since = {key: value for key, value in self.waiting_since.items() if key in active}

    def allowance(self, unit, start, end, budget_m, speed, driving):
        """Maximum metric progress this slice; zero records an actual wait."""
        if not self.active:
            return budget_m, None
        key = self.key(unit)
        if unit["stage"] in {"boarding_bus", "alighting_bus"}:
            key = unit.get("transit", {}).get("bus_id") or key
        allowed, reason = budget_m, None
        candidate = self.geometry.along(start, [end], driving, budget_m+1)
        if candidate:
            distance, zone = candidate
            if self.leases.get(zone, (None,))[0] != key:
                allowed = min(allowed, max(0, distance-.2))
                reason = "yielding at crossing" if driving else "waiting to cross"
        if driving:
            segment = length(start, end)
            if segment > 1e-8:
                dx, dy = (end[0]-start[0])/segment, (end[1]-start[1])/segment
                candidates = {other for cell in self.geometry.cells(start, end, 12/self.scale) for other in self.vehicle_grid[cell]}
                for other_key in candidates:
                    if other_key == key:
                        continue
                    other, _, _ = self.movers[other_key]
                    point = other["position"]
                    delta = ((point[0]-start[0])*self.scale, (point[1]-start[1])*self.scale)
                    ahead = delta[0]*dx+delta[1]*dy
                    lateral = abs(delta[0]*dy-delta[1]*dx)
                    heading = other.get("heading", unit.get("heading", 0))
                    same_direction = math.cos(heading)*dx+math.sin(heading)*dy > .5
                    if ahead > .01 and lateral < 2.2 and same_direction:
                        gap = 6.0+getattr(self, "headway_seconds", 1.2)*max(speed, 0)
                        if ahead-gap < allowed:
                            allowed, reason = max(0, ahead-gap), "waiting in traffic"
        return allowed, reason

    def driving_speed(self, unit, cruise, seconds):
        """Authored acceleration/braking; hard progress limits remain authoritative."""
        end = next((p for p in unit["route"] if length(p, unit["position"]) > 1e-8), None)
        target = cruise
        if end is not None and self.active:
            allowance, reason = self.allowance(unit, unit["position"], end, 35.0, cruise, True)
            if reason:
                target = min(cruise, math.sqrt(max(0, 2*3.0*getattr(self, "traction", 1.)*allowance)))
        previous = unit.get("current_speed", 0.0)
        traction = getattr(self, "traction", 1.)
        return max(0.05, min(previous+1.6*traction*seconds, max(previous-3.0*traction*seconds, target)))

    def snapshot(self):
        return {"version": "campus-traffic/1", "conflict_zones": len(self.geometry.points), "crossing_count": len(self.geometry.points),
                "waiting_pedestrians": sum(len(u["members"]) for u, driving, _ in self.movers.values() if not driving and u.get("traffic_wait")),
                "yielding_vehicles": sum(driving and u.get("traffic_wait") == "yielding at crossing" for u, driving, _ in self.movers.values()),
                "queued_vehicles": sum(driving and u.get("traffic_wait") == "waiting in traffic" for u, driving, _ in self.movers.values()),
                "active_reservations": len(self.leases), "wait_events": self.wait_events,
                "following_seconds": getattr(self, "headway_seconds", 1.2), "traction_factor": getattr(self, "traction", 1.),
                "assumptions": "geometric conflicts, first arrival with pedestrian tie priority, authored headway; no real traffic signals"}
