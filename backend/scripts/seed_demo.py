#!/usr/bin/env python3
"""Create two genuine simulator recordings and a persisted comparison via the live API."""
import argparse
import json
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    def request(path, data=None):
        req = urllib.request.Request(args.url + "/api" + path,
                                     data=json.dumps(data).encode() if data is not None else None,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)

    a = request("/runs", {"scenario_id": "riverside", "warning_id": "generic"})
    b = request("/runs", {"scenario_id": "riverside", "warning_id": "actionable", "baseline_run_id": a["id"]})
    c = request("/comparisons", {"baseline_run_id": a["id"], "alternative_run_id": b["id"]})
    print(json.dumps({"baseline": a["id"], "alternative": b["id"], "comparison": c["id"], "deltas": c["deltas"]}, indent=2))


if __name__ == "__main__":
    main()
