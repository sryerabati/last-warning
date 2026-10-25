"""Exercise real local inference, both warning runs, replay and comparisons."""
import json
import time
from pathlib import Path

import httpx


def main():
    base = "http://127.0.0.1:8000/api"
    client = httpx.Client(timeout=600)
    stimuli = client.get(base + "/stimuli").json()
    report = {"local_inference": [], "runs": []}
    analyses, runs = {}, {}
    for warning in ["generic", "actionable"]:
        stimulus = next(s for s in stimuli if s["warning_id"] == warning)
        started = time.monotonic()
        response = client.post(base + "/neural/local", json={"stimulus_id": stimulus["id"]})
        response.raise_for_status()
        analysis = response.json()
        assert analysis["provenance"] == "REAL_TRIBE" and analysis["model_id"] == "facebook/tribev2-mini"
        analyses[warning] = analysis
        row = {"warning": warning, "analysis_id": analysis["id"], "shape": analysis["prediction_shape"],
               "seconds": round(time.monotonic() - started, 2)}
        report["local_inference"].append(row)
        print(json.dumps(row), flush=True)
    for warning in ["generic", "actionable"]:
        body = {"scenario_id": "riverside", "warning_id": warning,
                "neural_analysis_id": analyses[warning]["id"], "coupling_strength": 0}
        if warning == "actionable":
            body["baseline_run_id"] = runs["generic"]["id"]
        response = client.post(base + "/runs", json=body)
        response.raise_for_status()
        run = response.json()
        runs[warning] = run
        report["runs"].append({"warning": warning, "run_id": run["id"],
            "initial_conditions_hash": run["initial_conditions_hash"], "metrics": run["metrics"]})
        recording = client.get(base + f"/runs/{run['id']}/frames").json()
        assert len(recording["frames"]) == run["frame_count"]
        assert recording["frames"][-1]["metrics"] == run["metrics"]
        print(json.dumps({"warning": warning, "sheltered": run["metrics"]["evacuated"],
                          "frames": run["frame_count"]}), flush=True)
    assert runs["generic"]["initial_conditions_hash"] == runs["actionable"]["initial_conditions_hash"]
    response = client.post(base + "/comparisons", json={"baseline_run_id": runs["generic"]["id"],
                                                       "alternative_run_id": runs["actionable"]["id"]})
    response.raise_for_status()
    report["comparison"] = response.json()
    response = client.post(base + "/neural/compare", json={"baseline_analysis_id": analyses["generic"]["id"],
                                                         "alternative_analysis_id": analyses["actionable"]["id"]})
    response.raise_for_status()
    report["neural_comparison"] = response.json()
    target = Path("output/e2e-demo.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2))
    print("END_TO_END_PASSED", flush=True)


if __name__ == "__main__":
    main()
