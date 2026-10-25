"""Repeatable local audit of a complete synthetic campus day; no model calls."""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.simulation.campus_life import DAY_VERSION, CampusLife


def audit(population=300, seed=42):
    started = time.perf_counter()
    life = CampusLife(population, seed)
    places = life.places
    home_households = Counter(h["home_place_id"] for h in life.households)
    family_households = [h for h in life.households if h["type"] == "family"]
    samples = []
    peak_park_waiting = peak_walking = peak_unreachable = 0
    stationary_walk_labels = Counter()
    for minute in range(0, 1441, 2):
        if minute:
            life.step(120)
        people = life.people
        modes = Counter(p["mode"] for p in people)
        parks = [p for p in people if places.get(p.get("place_id"), {}).get("kind") == "park"]
        park_waiting = sum(p["mode"] == "waiting" for p in parks)
        unreachable = sum(life.unit_for[p["id"]]["stage"] == "unreachable" for p in people)
        peak_park_waiting = max(peak_park_waiting, park_waiting)
        peak_walking = max(peak_walking, modes["walking"])
        peak_unreachable = max(peak_unreachable, unreachable)
        for p in people:
            if "walk" in p["activity"].lower() and p["mode"] == "waiting":
                stationary_walk_labels[p["activity"]] += 2
        if minute % 60 == 0:
            samples.append({"minute": minute, "modes": dict(modes),
                            "park_waiting": park_waiting, "unreachable": unreachable,
                            "activities": dict(Counter(p["activity"] for p in people))})
    return {
        "population": population, "seed": seed, "day_version": DAY_VERSION,
        "world_version": life.city.serialize()["world_version"],
        "elapsed_seconds": round(time.perf_counter()-started, 2),
        "roles": dict(Counter(p["role"] for p in life.profiles)),
        "family_households": len(family_households),
        "family_residents": sum(len(h["members"]) for h in family_households),
        "homes_used": len(home_households), "vehicles": len(life.vehicles),
        "family_homes": [{"id": h["home_place_id"], "name": places[h["home_place_id"]]["name"],
                          "building_type": places[h["home_place_id"]].get("building_type"),
                          "households_at_address": home_households[h["home_place_id"]]}
                         for h in family_households],
        "peak_park_waiting": peak_park_waiting, "peak_walking": peak_walking,
        "peak_unreachable": peak_unreachable,
        "stationary_walk_label_resident_minutes": dict(stationary_walk_labels),
        "hourly_samples": samples,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--population", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("output/campus-population-audit.json"))
    args = parser.parse_args()
    report = audit(args.population, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({k: v for k, v in report.items() if k != "hourly_samples"}, indent=2))
