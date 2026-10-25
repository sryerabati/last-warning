#!/usr/bin/env python3
"""Verify jobs, real Mini artifacts, replay paths and all disaster comparisons.

Default mode uses the rules baseline and no paid inference. Explicitly selecting
--decision-mode bedrock invokes the real resident provider under existing caps.
This creates isolated verification scenarios; it never edits the demo presets.
"""
import argparse
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.scripts.verify_disasters_demo import DISASTERS, LocalDemo, require, verify_disaster


class JobDemo(LocalDemo):
    def __init__(self, base_url, reuse_ids=()):
        super().__init__(base_url)
        self.jobs = []
        self.reuse = [super(JobDemo, self).json(f"/api/runs/{key}") for key in reuse_ids]

    def json(self, path, payload=None):
        if path == "/api/scenarios" and payload is not None:
            matching = next((run for run in self.reuse if all(
                run["configuration"].get(key) == value for key, value in payload.items() if key != "name")), None)
            if matching:
                return super().json(f"/api/scenarios/{matching['scenario_id']}")
        if path != "/api/runs" or payload is None:
            return super().json(path, payload)
        cached = next((run for run in self.reuse if run["scenario_id"] == payload["scenario_id"]
                       and run["warning_id"] == payload["warning_id"]
                       and run.get("baseline_run_id") == payload.get("baseline_run_id")
                       and run.get("neural_analysis_id") == payload.get("neural_analysis_id")), None)
        if cached:
            evidence = {"run_id": cached["id"], "status": "completed", "reused_completed_run": True}
            self.jobs.append(evidence)
            self.verify_motion(cached, evidence)
            return cached
        run, evidence = self.run_job(payload)
        self.verify_motion(run, evidence)
        return run

    def run_job(self, payload):
        request = {**payload, "idempotency_key": str(uuid.uuid4()), "analyze_warning": True}
        job = super().json("/api/run-jobs", request)
        duplicate = super().json("/api/run-jobs", request)
        require(job["id"] == duplicate["id"], "Duplicate submit scheduled another job")
        evidence = {"job_id": job["id"], "duplicate_submit_same_job": True, "progress": []}
        self.jobs.append(evidence)
        deadline = time.monotonic() + 700
        last = None
        while job["status"] in {"queued", "running"}:
            require(time.monotonic() < deadline, "Background run exceeded verification deadline")
            state = (job["stage"], job["progress"].get("tick"),
                     job["progress"].get("decision_rounds_completed"),
                     job["progress"].get("batches_completed"))
            if state != last:
                evidence["progress"].append({"stage": job["stage"], **job["progress"]})
                if state[0] != (last or (None,))[0]:
                    print(f"Job {job['id'][:8]}: {job['stage']} at tick {state[1]}", flush=True)
                last = state
            time.sleep(.4)
            job = super().json(f"/api/run-jobs/{job['id']}")
        evidence.update(status=job["status"], run_id=job.get("run_id"), final_progress=job["progress"])
        require(job["status"] == "completed", f"Job failed: {job.get('error')}")
        require(job["progress"]["tick"] == job["progress"]["total_ticks"], "Incomplete actual tick progress")
        run = super().json(f"/api/runs/{job['run_id']}")
        return run, evidence

    def verify_motion(self, run, evidence):
        recording = super().json(f"/api/runs/{run['id']}/frames")
        require(recording["recording_version"] == "last-warning-recording/2", "Missing additive motion recording")
        roads = {tuple(cell) for cell in recording["city"]["roads"]}
        previous = None
        total_paths = 0
        turning_paths = 0
        for frame in recording["frames"]:
            current = {row[0]: row[1:3] for row in frame["agents"]}
            for motion in frame.get("agent_motion", []):
                path, fractions = motion["path"], motion["fractions"]
                require(previous is not None, "Motion precedes initial frame")
                require(path[0] == previous[motion["id"]] and path[-1] == current[motion["id"]],
                        "Motion endpoint differs from actual resident position")
                require(len(path) == len(fractions) and fractions[0] == 0 and fractions[-1] == 1,
                        "Invalid presentation timing")
                for index, (start, end) in enumerate(pairwise(path)):
                    require(tuple(start) in roads and tuple(end) in roads, "Motion leaves a recorded road")
                    require(abs(start[0]-end[0]) + abs(start[1]-end[1]) == 1, "Motion skipped an edge")
                    require(fractions[index] < fractions[index+1], "Motion timing is not ordered")
                if len(path) > 2 and path[0][0] != path[-1][0] and path[0][1] != path[-1][1]:
                    turning_paths += 1
                total_paths += 1
            previous = current
        evidence.update(recorded_motion_paths=total_paths, recorded_turning_paths=turning_paths)
        require(total_paths > 0, "No actual movement recorded")
        person = recording["frames"][0]["agents"][0][0]
        detail = super().json(f"/api/runs/{run['id']}/residents/{person}?tick=0")
        require(detail["position"] == recording["frames"][0]["agents"][0][1:3], "Inspector position differs")
        require(detail["goal"] is not None and detail["initial_position"] is not None, "Missing real resident traits")
        evidence["resident_inspector_verified"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--decision-mode", choices=("rules", "bedrock"), default="rules")
    parser.add_argument("--disasters", nargs="+", choices=tuple(DISASTERS), default=list(DISASTERS))
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "pixel-world-e2e.json")
    parser.add_argument("--reuse-run", action="append", default=[], help="Reuse an explicitly selected completed run instead of billing it again")
    args = parser.parse_args()
    demo = JobDemo(args.base_url, args.reuse_run)
    report = {"started_at": datetime.now(UTC).isoformat(), "decision_mode": args.decision_mode,
              "verified": False, "disasters": [], "jobs": demo.jobs}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    try:
        report["budget_before"] = demo.json("/api/agents/status")["budget"]
        warnings = {warning["id"]: warning for warning in demo.json("/api/warnings")}
        for kind in args.disasters:
            result = verify_disaster(demo, kind, DISASTERS[kind], warnings, args.decision_mode)
            # Full AWS request diagnostics remain in the run ledger; keep this report readable.
            for run in result["runs"]:
                usage = run["agent_policy"].get("usage")
                if usage:
                    usage["request_evidence_count"] = len(usage.get("request_ids", []))
                    usage.pop("requests", None)
                    usage.pop("request_ids", None)
            report["disasters"].append(result)
            save()
        report["budget_after"] = demo.json("/api/agents/status")["budget"]
        require(report["budget_after"]["project_accounted_cost_usd"] < 30, "Project accounting exceeded $30")
        report.update(verified=True, finished_at=datetime.now(UTC).isoformat())
        save()
        print(f"PIXEL_DEMO_API_PASSED: {args.output}", flush=True)
    except Exception as error:
        report.update(error=f"{type(error).__name__}: {error}", finished_at=datetime.now(UTC).isoformat())
        save()
        raise


if __name__ == "__main__":
    main()
