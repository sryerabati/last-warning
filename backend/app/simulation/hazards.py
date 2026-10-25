"""Deterministic, deliberately uncalibrated hazard mechanisms for a fictional city.

Each wet cell activates its four neighbors after an edge transit time based on
river channel, elevation and local resistance. A priority queue schedules those
cellular transitions. Arrival depth increases with time; roads close at 0.30 m.
"""
import heapq
import math
from typing import Protocol

import numpy as np

from ..schemas import ScenarioConfig
from .world import SIZE, City, uniform


class Hazard(Protocol):
    cells: set[tuple[int, int]]
    active_cells: set[tuple[int, int]]
    danger_cells: set[tuple[int, int]]
    blocked: set[tuple[int, int]]

    def step(self, tick: int) -> None: ...

    def state(self) -> dict: ...


class Flood:
    def __init__(self, city: City, config: ScenarioConfig):
        self.city, self.config = city, config
        self.channel = set(city.river)
        self.arrival = np.full((SIZE, SIZE), np.inf)
        x, y = config.hazard_origin
        self.arrival[y, x] = 0
        self.pending = [(0.0, x, y)]
        self.wet: set[tuple[int, int]] = set()
        self.blocked: set[tuple[int, int]] = set()

    def step(self, tick: int):
        while self.pending and self.pending[0][0] <= tick:
            when, x, y = heapq.heappop(self.pending)
            if when != self.arrival[y, x] or (x, y) in self.wet:
                continue
            self.wet.add((x, y))
            for nx, ny in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]:
                if not (0 <= nx < SIZE and 0 <= ny < SIZE):
                    continue
                height = self.city.elevation[ny, nx]
                if height > 2.4:
                    continue
                channel = (nx, ny) in self.channel
                uphill = max(0, height - self.city.elevation[y, x])
                resistance = uniform(self.config.seed, "flood", nx, ny)
                transit = (1.1 if channel else 4.5 + 2 * resistance + 5 * uphill)
                candidate = when + transit / self.config.hazard_spread
                if candidate < self.arrival[ny, nx]:
                    self.arrival[ny, nx] = candidate
                    heapq.heappush(self.pending, (candidate, nx, ny))
        self.blocked = {p for p in self.wet if p in self.city.graph
                        and self.depth(p, tick) >= 0.3}

    def depth(self, pos: tuple[int, int], tick: int) -> float:
        x, y = pos
        if pos not in self.wet:
            return 0.0
        return min(1.8, 0.12 + 0.025 * (tick - self.arrival[y, x]))

    @property
    def cells(self):
        return self.wet

    @property
    def active_cells(self):
        return self.wet

    @property
    def danger_cells(self):
        return self.blocked

    def state(self):
        return {"type": "flood", "origin": list(self.config.hazard_origin)}


class Wildfire:
    """Neighbor ignition with wind, fuel resistance, uphill bias and finite burning.

    Roads represent combustible urban-interface verges. The river is a complete
    fuel break in this simplified model; spotting across water is not modeled.
    """

    wind = (0.8, 0.6)
    burn_ticks = 10

    def __init__(self, city: City, config: ScenarioConfig):
        self.city, self.config = city, config
        self.arrival = np.full((SIZE, SIZE), np.inf)
        x, y = config.hazard_origin
        self.arrival[y, x] = 0
        self.pending = [(0.0, x, y)]
        self.cells: set[tuple[int, int]] = set()
        self.active_cells: set[tuple[int, int]] = set()
        self.danger_cells: set[tuple[int, int]] = set()
        self.blocked: set[tuple[int, int]] = set()
        self.water = set(city.river)
        self.refuges = set(city.safe_zones)

    def step(self, tick: int):
        while self.pending and self.pending[0][0] <= tick:
            when, x, y = heapq.heappop(self.pending)
            if when != self.arrival[y, x] or (x, y) in self.cells:
                continue
            self.cells.add((x, y))
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                target = (nx, ny)
                if not (0 <= nx < SIZE and 0 <= ny < SIZE):
                    continue
                if target in self.water or target in self.refuges:
                    continue
                alignment = dx * self.wind[0] + dy * self.wind[1]
                wind_resistance = 1 - 0.65 * alignment
                uphill = max(0, self.city.elevation[ny, nx] - self.city.elevation[y, x])
                slope_resistance = 1 / (1 + 0.8 * uphill)
                fuel = 0.8 + 0.65 * uniform(self.config.seed, "fuel", nx, ny)
                road_resistance = 1.25 if target in self.city.graph else 1
                transit = 4.0 * wind_resistance * slope_resistance * fuel * road_resistance
                candidate = when + transit / self.config.hazard_spread
                if candidate < self.arrival[ny, nx]:
                    self.arrival[ny, nx] = candidate
                    heapq.heappush(self.pending, (candidate, nx, ny))
        self.active_cells = {p for p in self.cells if tick - self.arrival[p[1], p[0]] < self.burn_ticks}
        self.danger_cells = self.active_cells
        # Burned road verges stay closed for the replay: debris and hot surfaces
        # require inspection even after the modeled flame front has passed.
        self.blocked = self.cells.intersection(self.city.graph)

    def state(self):
        return {"type": "wildfire", "origin": list(self.config.hazard_origin), "wind": list(self.wind)}


class Tornado:
    """A moving wind footprint and a persistent, seed-derived debris swath.

    All residents are modeled outdoors at road nodes; designated local storm
    shelters replace the two distant flood refuges for this scenario.
    """

    direction = (0.8, -0.6)
    radius = 2.2
    damage_radius = 3.0
    start_tick = 12

    def __init__(self, city: City, config: ScenarioConfig):
        self.city, self.config = city, config
        self.cells: set[tuple[int, int]] = set()
        self.active_cells: set[tuple[int, int]] = set()
        self.danger_cells: set[tuple[int, int]] = set()
        self.blocked: set[tuple[int, int]] = set()
        self.center = tuple(float(v) for v in config.hazard_origin)
        self.refuges = set(city.safe_zones)
        self.started = False

    def step(self, tick: int):
        self.active_cells = set()
        self.started = tick >= self.start_tick
        if self.started:
            elapsed = (tick - self.start_tick) * 0.45 * self.config.hazard_spread
            ox, oy = self.config.hazard_origin
            self.center = (ox + self.direction[0] * elapsed, oy + self.direction[1] * elapsed)
            cx, cy = self.center
            # Interpolate the short segment traveled this tick: faster presets
            # cannot skip a thin strip of roads between recorded footprints.
            previous = max(0.0, elapsed - 0.45 * self.config.hazard_spread)
            px, py = ox + self.direction[0] * previous, oy + self.direction[1] * previous
            for y in range(max(0, math.floor(min(cy, py) - self.damage_radius)),
                           min(SIZE, math.ceil(max(cy, py) + self.damage_radius) + 1)):
                for x in range(max(0, math.floor(min(cx, px) - self.damage_radius)),
                               min(SIZE, math.ceil(max(cx, px) + self.damage_radius) + 1)):
                    pos = (x, y)
                    if pos in self.refuges:
                        continue
                    dx, dy = cx - px, cy - py
                    length2 = dx * dx + dy * dy
                    along = max(0, min(1, ((x - px) * dx + (y - py) * dy) / length2)) if length2 else 0
                    swept_distance = math.hypot(x - px - along * dx, y - py - along * dy)
                    if swept_distance <= self.damage_radius:
                        self.cells.add(pos)
                        if pos in self.city.graph and (
                            swept_distance <= self.radius or uniform(self.config.seed, "debris", x, y) < 0.55
                        ):
                            self.blocked.add(pos)
                    if swept_distance <= self.radius:
                        self.active_cells.add(pos)
        self.danger_cells = self.active_cells

    def state(self):
        return {"type": "tornado", "origin": list(self.config.hazard_origin),
                "center": list(self.center), "radius": self.radius,
                "wind": list(self.direction), "started": self.started}


def make_hazard(city: City, config: ScenarioConfig) -> Hazard:
    return {"flood": Flood, "wildfire": Wildfire, "tornado": Tornado}[config.disaster_type](city, config)
