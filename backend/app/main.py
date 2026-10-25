import hashlib
import math
import os
import subprocess
from itertools import pairwise
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from starlette.staticfiles import StaticFiles

from backend.scripts.run_tribe import OFFICIAL_CODE_REVISION
from backend.scripts.run_tribe_local import MODEL_ID, MODEL_REVISION, WORDS_PER_SECOND

from .bedrock import BedrockError, BedrockPolicy, BudgetExceeded, DecisionValidationError, agent_status
from .database import Store, identifier, now
from .jobs import JobConflict, RunJobs
from .local_tribe import LocalTribe
from .neuroscience import MAX_ARTIFACT_BYTES, SUPPORTED, AnalysisMetadata, compare_arrays, validate_artifact
from .schemas import (
    ComparisonRequest,
    LocalInferenceRequest,
    NeuralCompareRequest,
    RunJobRequest,
    RunRequest,
    ScenarioConfig,
    StrictModel,
    WarningConfig,
)
from .simulation import Simulation, simulate
from .simulation.campus_engine import VERSION as CAMPUS_VERSION
from .simulation.campus_life import CampusLife, campus_day
from .simulation.campus_world import DEFAULT_ORIGINS
from .simulation.engine import ART_MANIFEST_VERSION, STATES, VERSION
from .simulation.life import town_day

ROOT = Path(__file__).resolve().parents[2]
AGENT_BUDGET_ROOT = ROOT / "data" / "agents"


class AnalyzeWarningRequest(StrictModel):
    warning_id: str
    force: bool = False


def create_app(data_dir=None):
    app = FastAPI(title="Last Warning", version="0.1.0")
    store = Store(data_dir or os.environ.get("LAST_WARNING_DATA_DIR", ROOT / "data"))
    app.state.store = store
    jobs = RunJobs(store)
    app.state.run_jobs = jobs
    local_tribe = LocalTribe(ROOT)
    app.state.local_tribe = local_tribe
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type"])
    app.add_middleware(GZipMiddleware, minimum_size=1500, compresslevel=4)

    @app.exception_handler(KeyError)
    async def missing(request: Request, error: KeyError):
        return JSONResponse(status_code=404, content={"detail": error.args[0]})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "simulation_version": VERSION, "campus_simulation_version": CAMPUS_VERSION,
                "campus_default_origins": DEFAULT_ORIGINS, "gpu_required": False}

    @app.get("/api/agents/status")
    def agents_status():
        return agent_status(AGENT_BUDGET_ROOT)

    @app.get("/api/scenarios")
    def scenarios():
        return store.list("scenarios")

    @app.post("/api/scenarios", status_code=201)
    def new_scenario(value: ScenarioConfig):
        return store.put("scenarios", value.model_dump(mode="json"))

    def city_preview(config: ScenarioConfig):
        # Geometry preview never makes a model call or needs an agent policy.
        if config.layout == "campus":
            if os.environ.get("LAST_WARNING_NEURAL_INFERENCE") == "0" and config.town_life:
                from .day_preview import cache_path, cached_campus_day

                if cache_path(store.root, config).is_file():
                    day = cached_campus_day(store.root, config)
                    minute = config.town_start_minutes if config.town_start_minutes is not None else config.town_start_tick * 5
                    frame = day["frames"][min(len(day["frames"]) - 1, int(minute / day["minutes_per_tick"]))]
                    return {"city": day["city"], "frame": frame, "states": day["states"], "profiles": day["profiles"]}
            life = CampusLife(config.population, config.seed,
                              start_minute=config.town_start_minutes if config.town_start_minutes is not None else config.town_start_tick * 5,
                              campus_day_type=config.campus_day_type, transit_enabled=config.transit_enabled)
            return {"city": {**life.city.serialize(), "art_seed": config.seed,
                             "art_manifest_version": "last-warning-campus/2"},
                    "frame": life.frame(0), "states": STATES, "profiles": life.profiles}

        model = Simulation(config.model_copy(update={"decision_mode": "rules"}),
                           WarningConfig(name="Preview", text="Preview"))
        model.step()
        return {"city": {**model.city.serialize(), "art_seed": config.seed,
                         "art_manifest_version": ART_MANIFEST_VERSION},
                "frame": model.frames[0], "states": STATES}

    @app.post("/api/scenarios/preview")
    def draft_preview(value: ScenarioConfig):
        return city_preview(value)

    @app.post("/api/town-life/preview")
    def preview_town_life(value: ScenarioConfig):
        if not value.town_life:
            raise HTTPException(422, "Enable town life to request a daily recording")
        if value.layout == "campus":
            if os.environ.get("LAST_WARNING_NEURAL_INFERENCE") == "0":
                from .day_preview import streamed_campus_day

                return streamed_campus_day(store.root, value)
            return campus_day(value.population, value.seed, value.disaster_type,
                              campus_day_type=value.campus_day_type, transit_enabled=value.transit_enabled)
        return town_day(value.population, value.seed, value.disaster_type)

    @app.get("/api/scenarios/{key}")
    def scenario(key: str):
        return store.get("scenarios", key)

    @app.put("/api/scenarios/{key}")
    def save_scenario(key: str, value: ScenarioConfig):
        old = store.get("scenarios", key)
        return store.put("scenarios", {**value.model_dump(mode="json"), "created_at": old["created_at"]}, key)

    @app.get("/api/scenarios/{key}/preview")
    def preview(key: str):
        config = ScenarioConfig(**{k: v for k, v in store.get("scenarios", key).items() if k in ScenarioConfig.model_fields})
        return city_preview(config)

    @app.get("/api/warnings")
    def warnings():
        return store.list("warnings")

    @app.post("/api/warnings", status_code=201)
    def new_warning(value: WarningConfig):
        return store.put("warnings", value.model_dump(mode="json"))

    @app.put("/api/warnings/{key}")
    def save_warning(key: str, value: WarningConfig):
        old = store.get("warnings", key)
        return store.put("warnings", {**value.model_dump(mode="json"), "created_at": old["created_at"]}, key)

    @app.delete("/api/warnings/{key}", status_code=204)
    def delete_warning(key: str):
        store.delete("warnings", key)

    def run_snapshot(value: RunRequest):
        if os.environ.get("LAST_WARNING_NEURAL_INFERENCE") == "0" and (value.neural_analysis_id or value.coupling_strength):
            raise HTTPException(422, "Local model inference is not available on this Site")
        scenario = store.get("scenarios", value.scenario_id)
        warning = store.get("warnings", value.warning_id)
        config = ScenarioConfig(**{k: v for k, v in scenario.items() if k in ScenarioConfig.model_fields})
        if value.baseline_run_id:
            baseline = store.get("runs", value.baseline_run_id)
            if baseline["scenario_id"] != value.scenario_id:
                raise HTTPException(422, "An alternative must use its baseline's scenario")
            config = ScenarioConfig(**baseline["configuration"])
        return {"configuration": config.model_dump(mode="json"), "warning": warning}

    def execute_run(value: RunRequest, snapshot, progress_callback=None, cancel_check=None):
        if not store.run_slots.acquire(blocking=False):
            raise HTTPException(429, "Two simulations are already running. Try again shortly.")
        try:
            config = ScenarioConfig(**snapshot["configuration"])
            warning = snapshot["warning"]
            w = WarningConfig(**{k: v for k, v in warning.items() if k in WarningConfig.model_fields})
            adjustment = 0.0
            if value.coupling_strength and not value.neural_analysis_id:
                raise HTTPException(422, "Coupling requires a matching REAL_TRIBE analysis")
            if value.neural_analysis_id:
                analysis = store.get("analyses", value.neural_analysis_id)
                if analysis["provenance"] != "REAL_TRIBE" or analysis["warning_id"] != value.warning_id:
                    raise HTTPException(422, "The neural analysis must contain REAL_TRIBE data for this warning")
                text_hash = hashlib.sha256(w.text.encode()).hexdigest()
                if analysis["warning_text_hash"] != text_hash or analysis["stimulus_hash"] != text_hash:
                    raise HTTPException(422, "The warning text does not match this neural stimulus. Analyze the current warning again.")
                if not (store.root / "neural" / f"{analysis['id']}.npz").is_file():
                    raise HTTPException(422, "The neural artifact is missing. Analyze this warning again.")
                adjustment = value.coupling_strength * analysis["summary"]["normalized_feature"]
            if config.decision_mode == "bedrock" and value.coupling_strength:
                raise HTTPException(422, "TRIBE notice-probability coupling is available only in rules mode. "
                                    "Bedrock agents decide directly from their perceived warning.")
            policy = BedrockPolicy(AGENT_BUDGET_ROOT) if config.decision_mode == "bedrock" else None
            if policy is not None and progress_callback is not None:
                policy.progress_callback, policy.cancel_check = progress_callback, cancel_check
            try:
                recording = simulate(config, w, adjustment, decision_policy=policy,
                                     progress_callback=progress_callback, cancel_check=cancel_check)
            except BudgetExceeded as error:
                raise HTTPException(429, str(error)) from error
            except DecisionValidationError as error:
                raise HTTPException(502, str(error)) from error
            except BedrockError as error:
                raise HTTPException(503, str(error)) from error
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
            run_id = identifier()
            metadata = {k: v for k, v in recording.items()
                        if k not in {"frames", "events", "city", "states", "initial_conditions", "profiles"}}
            metadata.update(scenario_id=value.scenario_id, warning_id=value.warning_id,
                            baseline_run_id=value.baseline_run_id, neural_analysis_id=value.neural_analysis_id,
                            coupling_strength=value.coupling_strength, created_at=now(), frame_count=len(recording["frames"]))
            if cancel_check:
                cancel_check()
            store.write_recording(run_id, recording)
            try:
                return store.put("runs", metadata, run_id)
            except Exception:
                (store.root / "recordings" / f"{run_id}.json.gz").unlink(missing_ok=True)
                raise
        finally:
            store.run_slots.release()

    @app.post("/api/runs", status_code=201)
    def run(value: RunRequest):
        return execute_run(value, run_snapshot(value))

    @app.post("/api/run-jobs", status_code=202)
    def new_run_job(value: RunJobRequest):
        if os.environ.get("LAST_WARNING_NEURAL_INFERENCE") == "0" and value.analyze_warning:
            raise HTTPException(422, "Local model inference is not available on this Site")
        payload = value.model_dump(mode="json")
        request = RunRequest(**value.model_dump(exclude={"idempotency_key", "analyze_warning"}))
        # Existing idempotent requests resolve before looking at an edited or
        # deleted library entry. They never schedule replacement paid work.
        try:
            store.get("run_job_keys", value.idempotency_key)
            snapshot = {}
        except KeyError:
            snapshot = run_snapshot(request)

        def execute(key):
            job = store.get("run_jobs", key)
            snapshot = job["snapshot"]
            request = RunRequest(**{k: v for k, v in job["request"].items() if k in RunRequest.model_fields})
            def check_cancel():
                jobs.check_cancel(key)

            def progress(values):
                stage = values.get("stage", "simulation")
                jobs.update(key, stage=stage, progress={k: v for k, v in values.items() if k != "stage"})

            check_cancel()
            if job["request"]["analyze_warning"]:
                digest = hashlib.sha256(snapshot["warning"]["text"].encode()).hexdigest()
                if hashlib.sha256(store.get("warnings", request.warning_id)["text"].encode()).hexdigest() != digest:
                    raise HTTPException(409, "The warning changed while this job was queued. Create a new run for its current text.")
                jobs.update(key, stage="neural_queued")
                with jobs.neural_lock:
                    check_cancel()
                    jobs.update(key, stage="neural")
                    analysis = analyze_warning(AnalyzeWarningRequest(warning_id=request.warning_id))["analysis"]
                if analysis["stimulus_hash"] != digest:
                    raise HTTPException(409, "The analyzed text changed. Create a new run for the updated warning.")
                request = request.model_copy(update={"neural_analysis_id": analysis["id"]})
                jobs.update(key, analysis_id=analysis["id"])
            check_cancel()
            jobs.update(key, stage="simulation")
            return execute_run(request, snapshot, progress, check_cancel)

        try:
            return jobs.public(jobs.submit(payload, snapshot, execute))
        except JobConflict as error:
            raise HTTPException(409, str(error)) from error
        except BlockingIOError as error:
            raise HTTPException(429, str(error)) from error

    @app.get("/api/run-jobs")
    def run_jobs():
        return [jobs.public(j) for j in store.list("run_jobs")]

    @app.get("/api/run-jobs/{key}")
    def run_job(key: str):
        return jobs.public(store.get("run_jobs", key))

    @app.post("/api/run-jobs/{key}/cancel")
    def cancel_run_job(key: str):
        return jobs.public(jobs.cancel(key))

    @app.get("/api/runs")
    def runs():
        return store.list("runs")

    @app.get("/api/runs/{key}")
    def get_run(key: str):
        return store.get("runs", key)

    @app.get("/api/runs/{key}/frames")
    def frames(key: str, start: int = Query(0, ge=0), end: int | None = Query(None, ge=0)):
        recording = store.recording(key)
        if end is not None and end < start:
            raise HTTPException(422, "End must be greater than or equal to start")
        return {"city": {**recording["city"], "art_seed": recording.get("art_seed", recording.get("seed", 42)),
                         "art_manifest_version": recording.get("art_manifest_version", ART_MANIFEST_VERSION)},
                "states": recording["states"],
                "art_seed": recording.get("art_seed", recording.get("seed", 42)),
                "art_manifest_version": recording.get("art_manifest_version", ART_MANIFEST_VERSION),
                "recording_version": recording.get("recording_version"),
                "frames": recording["frames"][start:end], "total": len(recording["frames"]),
                **({"profiles": recording["profiles"], "town_day_version": recording.get("town_day_version")}
                   if recording.get("profiles") else {})}

    @app.get("/api/runs/{key}/residents/{resident_id}")
    def resident_detail(key: str, resident_id: int, tick: int | None = Query(None, ge=0)):
        recording = store.recording(key)
        frames = recording["frames"]
        index = len(frames) - 1 if tick is None else tick
        if index >= len(frames):
            raise HTTPException(422, "Tick is outside this saved recording")
        frame = frames[index]
        person = next((p for p in frame["agents"] if p[0] == resident_id), None)
        if person is None:
            raise HTTPException(404, "Resident not found")
        initial = next((p for p in recording.get("initial_conditions", {}).get("agents", [])
                        if p["id"] == resident_id), {})
        plan = None
        for previous in frames[:index + 1]:
            for route in previous.get("route_changes", []):
                if route["id"] == resident_id:
                    plan = route
        route = plan["path"] if plan else None
        if route and person[1:3] in route:
            route = route[route.index(person[1:3]):]
        campus = recording["city"].get("layout") == "campus"
        if campus and route:
            # A resident may lie between graph nodes. Trim at the nearest recorded
            # segment, retaining its current position as the visible route origin.
            position = person[1:3]
            if len(route) > 1 and position not in route:
                def segment_distance(i):
                    a, b = route[i], route[i + 1]
                    dx, dy = b[0] - a[0], b[1] - a[1]
                    t = max(0, min(1, ((position[0]-a[0])*dx+(position[1]-a[1])*dy)/(dx*dx+dy*dy or 1)))
                    return (position[0]-a[0]-t*dx)**2+(position[1]-a[1]-t*dy)**2
                nearest = min(range(len(route)-1), key=segment_distance)
                route = [position, *route[nearest+1:]] if segment_distance(nearest) < 1e-6 else None
        blocked = {tuple(p) for p in frame["blocked_roads"]}
        route_accessible = all(tuple(p) not in blocked for p in route) if route else None
        activity = next((a for a in frame.get("agent_activities", []) if a["id"] == resident_id), {})
        if campus and "route_accessible" in activity:
            route_accessible = activity["route_accessible"] if route else None
        elif campus and route:
            from types import SimpleNamespace

            from .simulation.campus_hazards import CampusHazard
            config = ScenarioConfig(**recording["configuration"])
            # Historical routes must use the map stored in their own recording.
            recorded_city = recording["city"]
            size = recorded_city.get("size", 40)
            hazard = CampusHazard(SimpleNamespace(size=size, map_bounds=recorded_city.get("map_bounds", [0, 0, size, size])), config)
            for previous in frames[:index+1]:
                hazard.step(previous["time"])
            from .simulation.campus_routes import segment_is_clear

            blocked_at = lambda point: hazard.blocked(point)
            if config.disaster_type == "public_safety":
                blocked_at.egress_score = lambda point: max(0., hazard.radius-math.dist(point, hazard.center)) if hazard.active else 0.
            route_accessible = (all(segment_is_clear(a, b, blocked_at, recorded_city.get("meters_per_unit", 24.25))
                                    for a, b in pairwise(route)) if len(route) > 1 else not blocked_at(route[0]))
        decision = next((d for d in frame.get("agent_decisions", []) if d["id"] == resident_id), None)
        activity = next((a for a in frame.get("agent_activities", []) if a["id"] == resident_id), {})
        return {"id": resident_id, "tick": frame["tick"], "time": frame["time"], "position": person[1:3],
                "state": recording["states"][person[3]], "exposure_seconds": person[4],
                "initial_position": initial.get("position"), "goal": initial.get("goal"),
                "trust": initial.get("trust"), "reaction_delay_ticks": initial.get("reaction_delay") if not initial.get("response_timing_seconds") else None,
                "response_timing_seconds": initial.get("response_timing_seconds"),
                "movement_speed_cells_per_tick": None if campus else initial.get("movement_speed"),
                "movement_speed_mps": initial.get("movement_speed") if campus else None,
                "current_speed_mps": activity.get("speed_mps"),
                "movement_style": activity.get("movement_style"),
                "weather_response": activity.get("weather_response"),
                "social_connections": initial.get("social_connections"), "decision": decision,
                "route": route, "destination": plan.get("destination") if plan else None,
                "route_source": "recorded_plan" if plan else None,
                "route_accessible": route_accessible,
                "art_seed": recording.get("art_seed", recording.get("seed", 42)),
                **({**{k: initial.get(k) for k in ("name", "household_id", "home_place_id", "work_place_id", "role")},
                    **{k: activity.get(k) for k in ("activity", "place_id", "inside", "partner_ids", "destination_place_id", "mode", "vehicle_id", "group_id")}}
                   if initial.get("household_id") else {})}

    @app.get("/api/runs/{key}/metrics")
    def metrics(key: str):
        recording = store.recording(key)
        return [{"tick": f["tick"], "time": f["time"], **f["metrics"]} for f in recording["frames"]]

    @app.get("/api/runs/{key}/events")
    def events(key: str):
        return store.recording(key)["events"]

    @app.get("/api/runs/{key}/export")
    def export_run(key: str):
        run = store.get("runs", key)
        return FileResponse(store.root / "recordings" / f"{run['id']}.json.gz",
                            media_type="application/gzip", filename=f"last-warning-{run['id']}.json.gz")

    @app.post("/api/comparisons", status_code=201)
    def new_comparison(value: ComparisonRequest):
        a = store.get("runs", value.baseline_run_id)
        b = store.get("runs", value.alternative_run_id)
        if a["id"] == b["id"]:
            raise HTTPException(422, "Choose two distinct runs")
        if a["initial_conditions_hash"] != b["initial_conditions_hash"] or a["simulation_version"] != b["simulation_version"]:
            raise HTTPException(422, "Comparison requires identical initial conditions and simulation versions")
        if a.get("decision_mode") == "bedrock":
            first = a["agent_policy"]["usage"]
            second = (b.get("agent_policy") or {}).get("usage") or {}
            if any(first.get(key) != second.get(key)
                   for key in ("provider", "model_id", "region", "decision_protocol")):
                raise HTTPException(422, "Comparison requires the same Bedrock model and decision protocol")
        deltas = {k: b["metrics"][k] - v if v is not None and b["metrics"][k] is not None else None
                  for k, v in a["metrics"].items() if (v is None or type(v) in (int, float)) and
                  (b["metrics"].get(k) is None or type(b["metrics"].get(k)) in (int, float))}
        assumptions = {k: {"baseline": v, "alternative": b["warning"][k]}
                       for k, v in a["warning"].items() if b["warning"][k] != v}
        assumptions["coupling_strength"] = {"baseline": a["coupling_strength"], "alternative": b["coupling_strength"]}
        return store.put("comparisons", {**value.model_dump(), "deltas": deltas, "assumptions": assumptions,
                                          "initial_conditions_hash": a["initial_conditions_hash"]})

    @app.get("/api/comparisons")
    def comparisons():
        return store.list("comparisons")

    @app.get("/api/comparisons/{key}")
    def get_comparison(key: str):
        return store.get("comparisons", key)

    @app.post("/api/stimuli", status_code=201)
    async def upload_stimulus(warning_id: Annotated[str, Form()], file: Annotated[UploadFile, File()]):
        warning = store.get("warnings", warning_id)
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in SUPPORTED:
            raise HTTPException(422, "Use TRIBE-compatible text, audio, or video")
        raw = await file.read(32 * 1024 * 1024 + 1)
        if not raw or len(raw) > 32 * 1024 * 1024:
            raise HTTPException(422, "Stimulus must be between 1 byte and 32 MiB")
        if suffix == ".txt":
            try:
                text = raw.decode("utf-8")
                if not text.strip():
                    raise ValueError("Empty text")
            except (UnicodeDecodeError, ValueError) as e:
                raise HTTPException(422, "Text stimulus must contain UTF-8 text") from e
        key = identifier()
        (store.root / "stimuli" / f"{key}{suffix}").write_bytes(raw)
        return store.put("stimuli", {"warning_id": warning_id, "filename": Path(file.filename).name,
                                     "suffix": suffix, "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw),
                                     "warning_text_hash": hashlib.sha256(warning["text"].encode()).hexdigest()}, key)

    @app.get("/api/stimuli")
    def stimuli():
        return store.list("stimuli")

    @app.get("/api/stimuli/{key}/download")
    def download_stimulus(key: str):
        value = store.get("stimuli", key)
        return FileResponse(store.root / "stimuli" / f"{value['id']}{value['suffix']}", filename=value["filename"])

    def save_analysis(stimulus_id, metadata, raw, local=False):
        stimulus = store.get("stimuli", stimulus_id)
        try:
            if len(metadata) > 32000:
                raise ValueError("Metadata is too large")
            meta = AnalysisMetadata.model_validate_json(metadata)
            store.get("warnings", meta.warning_id)
            if meta.warning_id != stimulus["warning_id"] or meta.stimulus_hash != stimulus["sha256"]:
                raise ValueError("Artifact warning or stimulus hash does not match the uploaded stimulus")
            summary, series = validate_artifact(raw, meta)
        except (ValueError, ValidationError, TypeError) as e:
            raise HTTPException(422, str(e)) from e
        key = identifier()
        (store.root / "neural" / f"{key}.npz").write_bytes(raw)
        return store.put("analyses", {**meta.model_dump(mode="json"), "summary": summary, "series": series,
                                      "stimulus_id": stimulus_id, "warning_text_hash": stimulus["warning_text_hash"],
                                      "provenance_note": ("Computed by this app's local official Mini worker." if local else
                                                          "Origin declared by imported metadata; not independently attested.")}, key)

    @app.post("/api/neural/import", status_code=201)
    async def import_analysis(stimulus_id: Annotated[str, Form()], metadata: Annotated[str, Form()],
                              file: Annotated[UploadFile, File()]):
        return save_analysis(stimulus_id, metadata, await file.read(MAX_ARTIFACT_BYTES + 1))

    @app.get("/api/neural/local")
    def local_status():
        return local_tribe.status()

    @app.post("/api/neural/local", status_code=201)
    def local_inference(value: LocalInferenceRequest):
        stimulus = store.get("stimuli", value.stimulus_id)
        output = store.root / "local-tribe" / "jobs" / identifier()
        try:
            metadata, raw = local_tribe.predict(stimulus,
                store.root / "stimuli" / f"{stimulus['id']}{stimulus['suffix']}", output)
            return save_analysis(stimulus["id"], metadata, raw, local=True)
        except FileNotFoundError as error:
            raise HTTPException(503, str(error)) from error
        except (UnicodeDecodeError, ValueError) as error:
            raise HTTPException(422, str(error)) from error
        except BlockingIOError as error:
            raise HTTPException(409, str(error)) from error
        except (RuntimeError, OSError) as error:
            raise HTTPException(500, str(error)) from error
        except subprocess.TimeoutExpired as error:
            raise HTTPException(504, "Local inference exceeded its ten-minute limit. The worker was stopped.") from error

    @app.post("/api/neural/analyze-warning")
    def analyze_warning(value: AnalyzeWarningRequest):
        warning = store.get("warnings", value.warning_id)
        raw = warning["text"].encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        if not value.force:
            for analysis in store.list("analyses"):
                sampling = analysis["sampling_information"]
                if (analysis["warning_id"] == value.warning_id and analysis["provenance"] == "REAL_TRIBE"
                    and analysis["model_id"] == MODEL_ID and analysis["model_revision"] == MODEL_REVISION
                    and analysis["code_revision"] == OFFICIAL_CODE_REVISION
                    and analysis["warning_text_hash"] == digest and analysis["stimulus_hash"] == digest
                    and sampling.get("stimulus_protocol") == "controlled_word_reading_v1"
                    and sampling.get("words_per_second") == WORDS_PER_SECOND
                    and (store.root / "neural" / f"{analysis['id']}.npz").is_file()):
                    return {"analysis": analysis, "cached": True}
        stimulus = next((s for s in store.list("stimuli") if s["warning_id"] == value.warning_id
                         and s["sha256"] == digest and s["warning_text_hash"] == digest and s["suffix"] == ".txt"
                         and (store.root / "stimuli" / f"{s['id']}.txt").is_file()), None)
        if stimulus is None:
            key = identifier()
            (store.root / "stimuli" / f"{key}.txt").write_bytes(raw)
            stimulus = store.put("stimuli", {"warning_id": value.warning_id, "filename": "warning.txt",
                "suffix": ".txt", "sha256": digest, "warning_text_hash": digest, "size": len(raw)}, key)
        analysis = local_inference(LocalInferenceRequest(stimulus_id=stimulus["id"]))
        current_hash = hashlib.sha256(store.get("warnings", value.warning_id)["text"].encode()).hexdigest()
        if current_hash != digest:
            raise HTTPException(409, "The warning changed during analysis. Run the updated warning again.")
        return {"analysis": analysis, "cached": False}

    @app.get("/api/neural/analyses")
    def analyses():
        return store.list("analyses")

    @app.get("/api/neural/analyses/{key}")
    def analysis(key: str):
        return store.get("analyses", key)

    @app.get("/api/neural/analyses/{key}/download")
    def download_analysis(key: str):
        value = store.get("analyses", key)
        return FileResponse(store.root / "neural" / f"{value['id']}.npz", filename=f"{value['id']}-predictions.npz")

    @app.get("/api/neural/analyses/{key}/metadata")
    def analysis_metadata(key: str):
        value = store.get("analyses", key)
        return {field: value[field] for field in AnalysisMetadata.model_fields if field in value}

    @app.post("/api/neural/compare")
    def neural_compare(value: NeuralCompareRequest):
        a = store.get("analyses", value.baseline_analysis_id)
        b = store.get("analyses", value.alternative_analysis_id)
        try:
            return compare_arrays(store.root / "neural" / f"{a['id']}.npz",
                                  store.root / "neural" / f"{b['id']}.npz", a, b)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    # A production build is served by the same local FastAPI process; Vite proxies /api in development.
    dist = ROOT / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(dist / "index.html")

    return app


app = create_app()
