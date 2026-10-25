# Pixel recording and background run API

The APIs preserve the existing synchronous `POST /api/runs` and immutable saved recordings. Living-town experiments use simulation version 1.4.0; their layout, daily start tick and profiles are part of their controlled initial conditions. Spending limits remain unchanged.

## Replay data

New recordings include `recording_version: "last-warning-recording/2"`, `art_seed` equal to the simulation seed and `art_manifest_version: "last-warning-pixel/1"`. These presentation fields do not enter the scenario or initial-condition hash. The frames endpoint returns them, and repeats appearance defaults in the city object for renderer use. Legacy recordings receive response-time appearance defaults without rewriting their saved files, metrics or hashes.

Each frame may contain `agent_motion: [{id, path, fractions}]`. Entries exist only for residents that moved during that tick. The path includes the actual starting vertex, every road edge traversed and the actual ending vertex. For example, a two-edge corner is `[[4,9],[3,9],[3,8]]`, with fractions `[0,0.5,1]`. Fractions specify equal-edge visual timing within the tick; they do not claim continuous pedestrian physics or measured substep times. A legacy transition without path evidence should snap when its route is ambiguous rather than interpolate across an invented diagonal.

`route_changes` stores sparse actual planned-route updates. Living-town routes can represent a real itinerary destination or emergency refuge. `GET /api/runs/{run_id}/residents/{resident_id}?tick=20` returns saved initial traits and goal, current recorded position/state/exposure, the latest recorded model decision and any recorded remaining plan. The endpoint never calls a model or invents absent legacy routes. `route_accessible` evaluates that last recorded plan against the selected frame's closures; it is not a guarantee that a waiting resident will follow it.

## Daily-life recording

`POST /api/town-life/preview` accepts a scenario and returns the organic city, resident `profiles`, 288 `frames`, `town_day_version: "riverside-life/1"`, `minutes_per_tick: 5`, and `clock_start_minutes: 0`. It runs locally and uses a bounded four-world cache. Day frames use the same road motion format as emergency replay, with no hazards. The UI begins at frame 96 (08:00).

The city includes named `places` with canonical footprints, entrances, facing, type and optional outdoor `activity_spots`, plus `road_styles` for road/path/bridge presentation. Each resident profile has a stable household, home, optional workplace, role and daily itinerary. Every frame records `world_clock_minutes`, `agent_activities` (place, destination, inside state and partners), and actual co-location `interactions` with participant IDs and expiry. These are saved simulation facts, not decorative dialogue. Profiles are shared recording-level data rather than repeated in every frame or run-library entry.

`town_start_tick` freezes the selected daily snapshot into a living-town emergency. Emergency frame zero preserves the selected positions and occupancy; subsequent world-clock advancement uses `tick_seconds / 60`, not the five-minute daily rate. Comparisons reuse that frozen configuration. New life-mode model decisions use `nova_resident_json_life_v1`, adding `CONTINUE_ROUTINE`; saved legacy experiments retain their existing protocol and geometry.

## Run jobs

`POST /api/run-jobs` accepts the usual run fields plus:

```json
{
  "scenario_id": "riverside",
  "warning_id": "generic",
  "analyze_warning": true,
  "coupling_strength": 0,
  "idempotency_key": "a-client-generated-uuid"
}
```

It returns HTTP 202 and a job ID. Poll `GET /api/run-jobs/{id}`; `GET /api/run-jobs` lists persisted jobs. A completed job supplies `run_id` and `analysis_id`; use the existing run/frame APIs to open the recording. The stored snapshot freezes the warning and scenario used for the experiment. If the warning changes before its queued neural stage, the job fails explicitly rather than analyzing one text and simulating another.

An idempotency key can identify only one exact request. Repeating it returns the same job, including after completion/failure or library edits; it never launches replacement paid work. Reusing it for different request fields returns HTTP 409. A deliberately new experiment or retry after fixing a failure requires a new key. Keys and jobs are inserted in one SQLite transaction with a unique primary key, so duplicate submissions cannot schedule two workers.

Statuses are `queued`, `running`, `completed`, `failed`, `cancelled` and `interrupted`. Stages include queued/local-neural waiting/local-neural execution, simulation and agent decisions. Progress reports actual saved tick, decision round/rounds completed and provider batches validated/total. Partial batches are not exposed as physical frames: the existing complete-round validation still precedes application of model actions. No fabricated overall percentage is provided.

There are two background workers and at most eight active/queued jobs. Job polling remains separate from compute. A neural-stage lock serializes jobs through the existing one-worker local Mini process. Simulations retain their existing two-run concurrency bound; synchronous requests still use that bound. SDK session/client creation and actual Bedrock requests share one global provider slot per service process, including across different run policies. TLS certificate verification stays enabled.

`POST /api/run-jobs/{id}/cancel` returns the updated job. Queued cancellation is immediately terminal. Running cancellation is cooperative: it prevents subsequent simulation work and provider reservations/requests, but cannot undo a call already sent or stop the already-running local Mini subprocess immediately. In-flight calls settle through the unchanged ledger; uncertain charges remain reserved. Cancellation between completion and response can leave a valid completed run, which the job reports as completed rather than discarding it.

Jobs interrupted by a dead server process are marked `interrupted` on recovery and are never resumed automatically. New jobs record a UUID worker identity whose advisory file lock is held until that worker exits; the operating system releases it after a crash, even if the PID remains as a zombie or is later reused. Legacy jobs without a worker identity use PID and process-state checks, treating zombies as dead. An unavailable legacy process-inspection tool conservatively preserves a potentially live job.

An old paid request may already have been billed. Recovery never creates replacement requests or releases uncertain spending reservations. Review the existing ledger and then submit a deliberate new key when another run is wanted. The provider continues using the same atomic spending ledger, $0.30 per-run limit, $5 phase cap and $30 project ceiling.
