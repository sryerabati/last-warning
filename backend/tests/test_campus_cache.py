import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from backend.app.simulation import campus_life


def test_concurrent_previews_build_one_day_and_share_across_hazards(monkeypatch):
    calls = []
    barrier = threading.Barrier(3)

    @lru_cache(maxsize=2)
    def build(population, seed, day_type, transit_enabled):
        calls.append((population, seed, day_type, transit_enabled))
        time.sleep(.05)  # Let simultaneous misses contend, as real generation does.
        return {"population": population, "seed": seed}

    monkeypatch.setattr(campus_life, "_campus_day", build)

    def preview(hazard):
        barrier.wait(timeout=5)
        return campus_life.campus_day(300, 42, hazard)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(preview, ["flood", "blizzard", "thunderstorm"]))
    assert calls == [(300, 42, "teaching", True)]
    assert all(result is results[0] for result in results)

    campus_life.campus_day(300, 42, "flood", "weekend", True)
    campus_life.campus_day(300, 42, "flood", "weekend", False)
    assert calls[-2:] == [(300, 42, "weekend", True), (300, 42, "weekend", False)]
