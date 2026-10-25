"""Authored educational hazard fields over a metric campus map.

Weather definitions come from NWS; this deterministic scenario profile is not a
weather forecast, damage model, or reconstruction of observed campus conditions.
All clocks below use simulated seconds, independent of playback/rendering speed.
"""
from __future__ import annotations

import math
from itertools import pairwise

from .world import uniform

SOURCES = {
    "blizzard": "https://www.weather.gov/iln/criteria-winter",
    "thunderstorm": "https://www.weather.gov/lot/SevereThunderstormWarningsUpdate",
    "hailstorm": "https://www.weather.gov/lot/SevereThunderstormWarningsUpdate",
    "lightning": "https://www.weather.gov/safety/lightning-tips",
    "public_safety": "https://dps.osu.edu/alert-notices",
}


def blizzard_criteria(wind_mph, visibility_miles, snowing, qualifying_seconds):
    """Local Wilmington inclusive thresholds; missing values never qualify."""
    values = (wind_mph, visibility_miles, qualifying_seconds)
    if any(v is None or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        return False
    return wind_mph >= 35 and 0 <= visibility_miles <= .25 and snowing is True and qualifying_seconds >= 10800


def thunderstorm_category(wind_mph=0, hail_inches=0):
    if wind_mph >= 80 or hail_inches >= 2.75:
        return "destructive"
    if wind_mph >= 70 or hail_inches >= 1.75:
        return "considerable"
    if wind_mph >= 58 or hail_inches >= 1:
        return "severe"
    return "ordinary"


class CampusHazard:
    def __init__(self, city, config):
        self.city, self.config = city, config
        self.size = getattr(city, "size", 40)
        self.weather_radius = max(60., math.sqrt(2) * self.size)
        bounds = getattr(city, "map_bounds", [0, 0, self.size, self.size])
        self.domain_cells = {(x, y) for x in range(self.size) for y in range(self.size)
                             if bounds[0] <= x + .5 <= bounds[2] and bounds[1] <= y + .5 <= bounds[3]}
        self.kind = config.disaster_type
        self.origin = tuple(float(v) for v in config.hazard_origin)
        self.center = self.origin
        self.seconds = 0.
        self.radius = 0.
        self.active = False
        self.all_clear = False
        self.last_thunder = None
        self.qualifying_seconds = 0.
        self.cells = set()
        self.active_cells = set()
        self.blocked_cells = set()
        self.debris_cells = set()
        self.version = 0

    def step(self, seconds, rasterize=True):
        if seconds < self.seconds:
            raise ValueError("Hazard time cannot run backwards; replay uses recorded frames")
        previous_seconds = self.seconds
        self.seconds = float(seconds)
        t, strength = self.seconds, self.config.hazard_spread
        self.center = self.origin
        if self.kind == "blizzard":
            self.active = 0 <= t < 12600
            self.all_clear = t >= 12600
            self.radius = self.weather_radius
            self.qualifying_seconds = min(t, 12600.)
        elif self.kind in {"hailstorm", "thunderstorm"}:
            last = 1200 if self.kind == "hailstorm" else 1800
            self.active = 120 <= t <= last
            self.radius = self.weather_radius
            if t >= 120:
                # A declared sequence of thunder observations; a later report
                # resets the hold even if the visual rain has eased.
                self.last_thunder = min(last, math.floor(t / 120) * 120)
            self.all_clear = self.last_thunder is not None and t - self.last_thunder >= 1800
        elif self.kind == "public_safety":
            self.active = 30 <= t < 900
            self.all_clear = t >= 900
            self.radius = 3.3 if t < 300 else 4.2
        elif self.kind == "flood":
            self.active = t >= 30
            self.radius = min(7., .8 + max(0, t-30) / 160 * strength)
        elif self.kind == "wildfire":
            self.active = t >= 45
            self.radius = min(7., .6 + max(0, t-45) / 150 * strength)
            self.center = (self.origin[0] + min(3., t / 240), self.origin[1] - min(1., t / 720))
        elif self.kind == "tornado":
            self.active = 30 <= t <= 180
            elapsed = max(0, min(t, 180)-30)
            self.center = (self.origin[0] + elapsed * .15 * strength,
                           self.origin[1] - elapsed * .09 * strength)
            self.radius = 1.8
            self.all_clear = t >= 300
        else:
            raise ValueError(f"Unsupported campus hazard {self.kind}")
        self.version = 3 if self.all_clear else 2 if t >= 300 else 1 if t >= 30 else 0
        # Raster sampling is only a display operation. Movement and contact use
        # the continuous field. Tornado debris follows the swept ground track,
        # even when a recording interval jumps over the entire active phase.
        if self.kind == "tornado" and previous_seconds <= 180 and t >= 30:
            a, b = self.field_at(max(30, previous_seconds))[1], self.field_at(min(180, t))[1]
            swept = {p for p in self.domain_cells
                     if min(a[0], b[0])-1.8 <= p[0]+.5 <= max(a[0], b[0])+1.8
                     and min(a[1], b[1])-1.8 <= p[1]+.5 <= max(a[1], b[1])+1.8
                     and self.contact_intervals((p[0]+.5, p[1]+.5), (p[0]+.5, p[1]+.5), previous_seconds, t)}
            self.cells.update(swept)
            self.debris_cells.update(p for p in swept
                                     if uniform(self.config.seed, "campus-debris", *p) < .18)
        if rasterize:
            self.active_cells = {(x, y) for x, y in self.domain_cells
                                 if self.danger_at((x+.5, y+.5))}
            self.cells.update(self.active_cells)
            self.blocked_cells = {(x, y) for x, y in self.domain_cells
                                  if self.blocked((x+.5, y+.5))}

    def field_at(self, seconds):
        """Pure time sampling for exposure integration; never mutates replay state."""
        t, strength = seconds, self.config.hazard_spread
        center = self.origin
        if self.kind == "blizzard":
            return 0 <= t < 12600, center, self.weather_radius
        if self.kind in {"hailstorm", "thunderstorm"}:
            return 120 <= t <= (1200 if self.kind == "hailstorm" else 1800), center, self.weather_radius
        if self.kind == "public_safety":
            return 30 <= t < 900, center, 3.3 if t < 300 else 4.2
        if self.kind == "flood":
            return t >= 30, center, min(7., .8 + max(0, t-30)/160*strength)
        if self.kind == "wildfire":
            center = (self.origin[0]+min(3., t/240), self.origin[1]-min(1., t/720))
            return t >= 45, center, min(7., .6+max(0, t-45)/150*strength)
        elapsed = max(0, min(t, 180)-30)
        center = (self.origin[0]+elapsed*.15*strength, self.origin[1]-elapsed*.09*strength)
        return 30 <= t <= 180, center, 1.8

    def contact_intervals(self, start, end, start_seconds, end_seconds):
        """Exact circle contact for piecewise-linear people and authored fields.

        The radius may grow linearly. Splitting at field breakpoints makes the
        quadratic relative-motion intersection independent of output frame rate.
        Tangency has zero exposure duration and does not cause a knockdown.
        """
        if end_seconds <= start_seconds:
            return []
        strength = self.config.hazard_spread
        cuts = {start_seconds, end_seconds}
        boundaries = [0., 30., 45., 120., 180., 300., 720., 900., 1200., 1800., 12600.,
                      30+(7.-.8)*160/strength, 45+(7.-.6)*150/strength]
        cuts.update(t for t in boundaries if start_seconds < t < end_seconds)
        duration = end_seconds-start_seconds
        def point(at):
            f = (at-start_seconds)/duration
            return tuple(start[i]+(end[i]-start[i])*f for i in (0, 1))
        result = []
        ordered = sorted(cuts)
        for left, right in pairwise(ordered):
            if not self.field_at((left+right)/2)[0]:
                continue
            _, ca, ra = self.field_at(left)
            _, cb, rb = self.field_at(right)
            if self.kind == "public_safety":
                ra = rb = self.field_at((left+right)/2)[2]
            pa, pb = point(left), point(right)
            a = tuple(pa[i]-ca[i] for i in (0, 1))
            v = tuple(pb[i]-cb[i]-a[i] for i in (0, 1))
            dr = rb-ra
            aa = sum(n*n for n in v)-dr*dr
            bb = 2*sum(a[i]*v[i] for i in (0, 1))-2*ra*dr
            cc = sum(n*n for n in a)-ra*ra
            roots = [0., 1.]
            if abs(aa) < 1e-12:
                if abs(bb) > 1e-12:
                    roots.append(-cc/bb)
            else:
                discriminant = bb*bb-4*aa*cc
                if discriminant >= 0:
                    square = math.sqrt(discriminant)
                    roots.extend(((-bb-square)/(2*aa), (-bb+square)/(2*aa)))
            roots = sorted({max(0., min(1., value)) for value in roots})
            for begin, finish in pairwise(roots):
                middle = (begin+finish)/2
                if finish-begin <= 1e-10 or aa*middle*middle+bb*middle+cc > 1e-9:
                    continue
                interval = (left+begin*(right-left), left+finish*(right-left))
                if result and abs(result[-1][1]-interval[0]) < 1e-8:
                    result[-1] = (result[-1][0], interval[1])
                else:
                    result.append(interval)
        return result

    def motion(self, start_seconds, end_seconds):
        """Recorded ground-center path and active fractions for faithful replay."""
        if end_seconds <= start_seconds:
            return None
        cuts = sorted({start_seconds, end_seconds, *[t for t in (30., 180., 720.)
                                                    if start_seconds < t < end_seconds]})
        duration = end_seconds-start_seconds
        active_windows = {"tornado": (30., 180.), "public_safety": (30., 900.),
                          "hailstorm": (120., 1200.), "thunderstorm": (120., 1800.),
                          "blizzard": (0., 12600.), "flood": (30., math.inf),
                          "wildfire": (45., math.inf)}
        begin, finish = active_windows[self.kind]
        left, right = max(begin, start_seconds), min(finish, end_seconds)
        active = right > left
        return {"path": [list(self.field_at(t)[1]) for t in cuts],
                "fractions": [(t-start_seconds)/duration for t in cuts],
                "active_from": (left-start_seconds)/duration if active else None,
                "active_until": (right-start_seconds)/duration if active else None}

    def danger_at(self, pos, seconds=None):
        active, center, radius = ((self.active, self.center, self.radius) if seconds is None else self.field_at(seconds))
        return active and math.dist(pos, center) <= radius

    def blocked(self, pos):
        """Hard closures, distinct from weather that merely makes travel unwise."""
        if self.kind in {"flood", "wildfire", "public_safety"}:
            return self.danger_at(pos)
        if self.kind == "tornado":
            return self.danger_at(pos) or (math.floor(pos[0]), math.floor(pos[1])) in self.debris_cells
        return False

    @property
    def speed_factor(self):
        if not self.active:
            return 1.
        return .45 if self.kind == "blizzard" else .75 if self.kind in {"hailstorm", "thunderstorm"} else 1.

    def mobility_conditions(self):
        """Authored campus traction/pace assumptions, not measured road speeds.

        The snow remains after an all-clear: ending falling snow does not plow a
        path or restore tire grip. These factors are distinct from warning intent.
        """
        if self.kind == "blizzard":
            cover = min(1., self.qualifying_seconds/5400.)
            return {"response": "snow_caution", "walk_factor": (.72-.17*cover) if self.active else (.8-.15*cover),
                    "vehicle_factor": (.5-.18*cover) if self.active else (.72-.2*cover),
                    "headway_seconds": 3., "traction": .5}
        if self.active and self.kind in {"hailstorm", "thunderstorm"}:
            return {"response": "storm_caution", "walk_factor": .85, "vehicle_factor": .7,
                    "headway_seconds": 2., "traction": .75}
        return {"response": "none", "walk_factor": 1., "vehicle_factor": 1.,
                "headway_seconds": 1.2, "traction": 1.}

    def suitable(self, place, seconds=None):
        if not place or not place.get("solid_building", place.get("kind") not in {"park"}):
            return False
        # Capacities and protective features are authored in the campus overlay,
        # never claims that a named landmark is an official designated shelter.
        if place.get("shelter_eligible") is False:
            return False
        if self.kind in {"flood", "wildfire"}:
            _, center, radius = ((self.active, self.center, self.radius) if seconds is None else self.field_at(seconds))
            return math.dist(place["entrance"], center) > radius + 1.
        if self.kind == "tornado":
            return place.get("kind") not in {"parking", "stadium"} and place.get("storm_shelter", True)
        return True

    def protected(self, person, places, seconds=None):
        # Car bodies are not universal shelter. This conservative model counts
        # only eligible building occupancy as full storm protection.
        return bool(person.get("inside") and self.suitable(places.get(person.get("place_id")), seconds))

    @staticmethod
    def outside_scene(person, places):
        # A boundary portal is an off-map household, not a building at that point.
        return bool(person.get("inside") and places.get(person.get("place_id"), {}).get("is_portal"))

    def state(self):
        t = self.seconds
        weather = self.kind in {"blizzard", "hailstorm", "thunderstorm"}
        wind = 40 if self.kind == "blizzard" else 85 if self.kind == "thunderstorm" else 45 if self.kind == "hailstorm" else 0
        hail = 2.75 if self.kind == "thunderstorm" else 1.75 if self.kind == "hailstorm" else 0
        hold = max(0, 1800 - (t - self.last_thunder)) if self.last_thunder is not None else 0
        return {
            "type": self.kind, "origin": list(self.origin), "center": list(self.center),
            "radius": self.radius, "ground_radius": self.radius, "ground_center": list(self.center), "wind": [1., -.25], "started": t >= 30,
            "active": self.active, "all_clear": self.all_clear, "elapsed_seconds": t,
            "phase": "all_clear" if self.all_clear else "active" if self.active else "shelter_hold" if hold else "approaching",
            "intensity": 1. if self.active else .15 if hold else 0.,
            "wind_mph": wind if self.active else 8, "hail_inches": hail if self.active else 0.,
            "visibility_miles": .2 if self.kind == "blizzard" and self.active else 10.,
            "temperature_c": -12 if self.kind == "blizzard" else 18,
            "snowing": self.kind == "blizzard" and self.active,
            "qualifying_blizzard_seconds": self.qualifying_seconds,
            "blizzard_criteria_met": self.kind == "blizzard" and blizzard_criteria(40, .2, True, self.qualifying_seconds),
            "damage_threat": thunderstorm_category(wind, hail) if self.kind in {"hailstorm", "thunderstorm"} else None,
            "last_thunder_seconds": self.last_thunder, "shelter_hold_seconds_remaining": hold,
            "instruction_version": self.version, "simulation": True,
            "protective_action": "avoid_area" if self.kind == "public_safety" else "seek_suitable_shelter",
            "profile_provenance": "authored", "criteria_source": SOURCES.get(self.kind),
            "geometry_provenance": "authored hazard field over sourced map geometry",
            "weather_profile": "Educational scenario; not observed campus weather" if weather else None,
        }
