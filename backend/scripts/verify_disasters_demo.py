#!/usr/bin/env python3
"""Verify the running local demo with real Mini artifacts and new isolated scenarios.

This is an explicit end-to-end verifier, not a pytest test. It may run the local
Mini worker when a warning lacks a matching cached analysis. It never edits a
stored warning or scenario. The default rules mode makes no cloud calls; explicitly
selecting --decision-mode bedrock invokes paid resident decisions under the app's caps.
"""
import argparse
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

if __package__:
    from .run_tribe import OFFICIAL_CODE_REVISION
    from .run_tribe_local import MODEL_ID, MODEL_REVISION, WORDS_PER_SECOND
else:
    from run_tribe import OFFICIAL_CODE_REVISION
    from run_tribe_local import MODEL_ID, MODEL_REVISION, WORDS_PER_SECOND

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DISASTERS = {
    "flood": {"warnings": ("generic", "actionable"), "sheltered": (188, 235)},
    "wildfire": {"warnings": ("generic-wildfire", "actionable-wildfire"), "sheltered": (87, 185)},
    "tornado": {"warnings": ("generic-tornado", "actionable-tornado"), "sheltered": (52, 172)},
}


def require(condition, description):
    if not condition:
        raise ValueError(description)


class LocalDemo:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def raw(self, path, payload=None):
        request = Request(self.base_url + path, data=json.dumps(payload).encode() if payload is not None else None,
                          headers={"Content-Type": "application/json"} if payload is not None else {})
        try:
            with urlopen(request, timeout=700) as response:
                return response.read()
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:2000]
            raise RuntimeError(f"{request.get_method()} {path}: HTTP {error.code}: {detail}") from error

    def json(self, path, payload=None):
        return json.loads(self.raw(path, payload))


def verify_artifact(demo, warning):
    warning_id = warning["id"]
    print(f"Analyzing {warning_id} with the local Mini worker (matching cache allowed)", flush=True)
    response = demo.json("/api/neural/analyze-warning", {"warning_id": warning_id})
    analysis = response["analysis"]
    digest = hashlib.sha256(warning["text"].encode("utf-8")).hexdigest()
    require(analysis["warning_id"] == warning_id, f"Wrong warning bound to analysis for {warning_id}")
    require(analysis["provenance"] == "REAL_TRIBE", f"Fixture or absent real inference for {warning_id}")
    require(analysis["model_id"] == MODEL_ID and analysis["model_revision"] == MODEL_REVISION,
            f"Unexpected model or checkpoint for {warning_id}")
    require(analysis["code_revision"] == OFFICIAL_CODE_REVISION, f"Unpinned TRIBE code for {warning_id}")
    require(analysis["stimulus_hash"] == analysis["warning_text_hash"] == digest,
            f"Neural stimulus is not the exact current warning for {warning_id}")
    sampling = analysis["sampling_information"]
    require(sampling["stimulus_protocol"] == "controlled_word_reading_v1"
            and sampling["words_per_second"] == WORDS_PER_SECOND, f"Unexpected reading protocol for {warning_id}")
    raw = demo.raw(f"/api/neural/analyses/{analysis['id']}/download")
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        require(set(archive.files) == {"predictions", "times"}, f"Unexpected NPZ entries for {warning_id}")
        values, times = archive["predictions"], archive["times"]
        require(values.ndim == 2 and values.shape[0] > 0 and values.shape[1] == 20484,
                f"Expected a time × 20,484 cortical-vertex prediction for {warning_id}")
        require(list(values.shape) == analysis["prediction_shape"], f"Artifact shape mismatch for {warning_id}")
        require(times.ndim == 1 and len(times) == len(values) and np.all(np.diff(times) > 0),
                f"Invalid neural time axis for {warning_id}")
        require(np.isfinite(values).all() and np.isfinite(times).all(), f"Nonfinite neural result for {warning_id}")
        require(float(values.std()) > 0, f"Unexpected constant neural prediction for {warning_id}")
        result = {"warning_id": warning_id, "analysis_id": analysis["id"], "stimulus_id": analysis["stimulus_id"],
                  "cached": response["cached"], "warning_text_sha256": digest,
                  "artifact_sha256": hashlib.sha256(raw).hexdigest(), "artifact_bytes": len(raw),
                  "prediction_shape": list(values.shape), "time_seconds": times.tolist(),
                  "minimum": float(values.min()), "maximum": float(values.max()),
                  "standard_deviation": float(values.std()), "provenance": analysis["provenance"]}
    print(f"Verified {warning_id}: shape {result['prediction_shape']}, cached={response['cached']}", flush=True)
    return result


def verify_disaster(demo, kind, settings, warnings, decision_mode="rules"):
    # Every verifier run uses fresh scenario IDs. Riverside is being used by the
    # interactive demo and is deliberately never mutated here.
    scenario = demo.json("/api/scenarios", {"name": f"Riverside {kind} verification", "disaster_type": kind,
                         "population": 300, "seed": 42, "duration_ticks": 120, "tick_seconds": 5,
                         "hazard_spread": 1.0, "decision_mode": decision_mode})
    result = {"disaster_type": kind, "scenario_id": scenario["id"], "scenario": scenario,
              "warnings": [], "runs": []}
    for warning_id in settings["warnings"]:
        require(warning_id in warnings, f"Seed warning {warning_id} is missing")
        result["warnings"].append(verify_artifact(demo, warnings[warning_id]))
    recordings = []
    for i, warning_id in enumerate(settings["warnings"]):
        body = {"scenario_id": scenario["id"], "warning_id": warning_id,
                "neural_analysis_id": result["warnings"][i]["analysis_id"], "coupling_strength": 0}
        if i:
            body["baseline_run_id"] = result["runs"][0]["run_id"]
        run = demo.json("/api/runs", body)
        if decision_mode == "rules":
            require(run["metrics"]["evacuated"] == settings["sheltered"][i],
                    f"Unexpected {kind}/{warning_id} sheltered count: {run['metrics']['evacuated']}")
        require(run["neural_analysis_id"] == body["neural_analysis_id"] and run["notice_adjustment"] == 0,
                f"Analysis attachment or zero-coupling behavior failed for {warning_id}")
        require(run["configuration"]["disaster_type"] == kind, f"Wrong simulated hazard for {warning_id}")
        frames = demo.json(f"/api/runs/{run['id']}/frames")
        require(len(frames["frames"]) == frames["total"] == 121, f"Incomplete replay for {warning_id}")
        for frame in frames["frames"]:
            require(frame["hazard"]["type"] == kind, f"Replay uses the wrong hazard for {warning_id}")
            require(len(frame["agents"]) == sum(frame["metrics"]["state_counts"].values()) == 300,
                    f"Replay lost population for {warning_id} at tick {frame['tick']}")
        require(frames["frames"][-1]["metrics"] == run["metrics"], f"Final replay metrics differ for {warning_id}")
        events = demo.json(f"/api/runs/{run['id']}/events")
        if decision_mode == "bedrock":
            policy = run["agent_policy"]
            usage = policy["usage"]
            decisions = [event for event in events if event["type"] == "agent_model_decision"]
            require(policy["mode"] == "bedrock" and usage["provider"] == "aws_bedrock"
                    and usage["model_id"] == "us.amazon.nova-micro-v1:0", "Wrong resident decision provider")
            require(len(decisions) == policy["decision_count"] > 0, "Missing actual model decision history")
            require(usage["calls"] > 0 and usage["input_tokens"] > 0 and usage["output_tokens"] > 0,
                    "Missing Bedrock token usage")
            require(len(usage["request_ids"]) == usage["calls"], "Missing AWS request evidence")
            require(0 < usage["estimated_cost_usd"] <= usage["accounted_cost_usd"] <= .30,
                    "Bedrock run exceeded its accounting limit")
            require(usage["uncertain_or_pending_calls"] == 0, "Unsettled calls in a completed run")
            require(all(value["tick"] <= frame["tick"] for frame in frames["frames"]
                        for value in frame["agent_decisions"]), "Replay exposed a future model decision")
        require(any(e["type"] == "warning_delivered" for e in events), f"Missing warning delivery for {warning_id}")
        require(any(e["type"] == "agent_reached_safety" for e in events), f"Missing actual shelter arrival for {warning_id}")
        recordings.append(frames)
        result["runs"].append({"warning_id": warning_id, "run_id": run["id"],
            "neural_analysis_id": run["neural_analysis_id"], "initial_conditions_hash": run["initial_conditions_hash"],
            "simulation_version": run["simulation_version"], "metrics": run["metrics"],
            "frame_count": len(frames["frames"]), "event_count": len(events),
            "agent_policy": run["agent_policy"]})
        print(f"Verified {kind}/{warning_id}: {run['metrics']['evacuated']} sheltered, "
              f"{run['metrics']['exposed']} exposed", flush=True)
    a, b = result["runs"]
    require(a["initial_conditions_hash"] == b["initial_conditions_hash"], f"Different initial conditions for {kind}")
    for x, y in zip(recordings[0]["frames"], recordings[1]["frames"], strict=True):
        require(x["hazard_cells"] == y["hazard_cells"] and x["active_hazard_cells"] == y["active_hazard_cells"]
                and x["blocked_roads"] == y["blocked_roads"], f"Warning changed the actual {kind} hazard")
    comparison = demo.json("/api/comparisons", {"baseline_run_id": a["run_id"], "alternative_run_id": b["run_id"]})
    require(comparison["deltas"]["evacuated"] == b["metrics"]["evacuated"] - a["metrics"]["evacuated"],
            f"Wrong shelter difference for {kind}")
    neural = demo.json("/api/neural/compare", {"baseline_analysis_id": result["warnings"][0]["analysis_id"],
        "alternative_analysis_id": result["warnings"][1]["analysis_id"]})
    require(neural["provenance"] == "REAL_TRIBE" and neural["aligned_samples"] > 0,
            f"Neural comparison could not align real predictions for {kind}")
    require(np.isfinite(neural["mean_absolute_difference"]), f"Nonfinite neural comparison for {kind}")
    result["comparison"] = comparison
    result["neural_comparison"] = neural
    result["verified"] = True
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "output" / "e2e-disasters.json")
    parser.add_argument("--decision-mode", choices=("rules", "bedrock"), default="rules")
    parser.add_argument("--disasters", nargs="+", choices=tuple(DISASTERS), default=list(DISASTERS))
    args = parser.parse_args(argv)
    demo = LocalDemo(args.base_url)
    report = {"started_at": datetime.now(UTC).isoformat(), "base_url": args.base_url,
              "model_id": MODEL_ID, "model_revision": MODEL_REVISION, "code_revision": OFFICIAL_CODE_REVISION,
              "decision_mode": args.decision_mode, "cloud_inference_spend_usd": 0,
              "verified": False, "disasters": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    save()
    try:
        report["health"] = demo.json("/api/health")
        warnings = {warning["id"]: warning for warning in demo.json("/api/warnings")}
        for kind in args.disasters:
            report["disasters"].append(verify_disaster(demo, kind, DISASTERS[kind], warnings, args.decision_mode))
            report["cloud_inference_spend_usd"] = sum(
                (run["agent_policy"]["usage"] or {}).get("estimated_cost_usd", 0)
                for disaster in report["disasters"] for run in disaster["runs"])
            save()
        if args.decision_mode == "bedrock":
            report["agent_status"] = demo.json("/api/agents/status")
        report.update(verified=True, finished_at=datetime.now(UTC).isoformat())
        save()
        print(f"All {len(args.disasters)} selected disasters verified. Evidence: {args.output.resolve()}", flush=True)
    except Exception as error:
        report.update(error=f"{type(error).__name__}: {error}", finished_at=datetime.now(UTC).isoformat())
        save()
        raise


if __name__ == "__main__":
    main()
