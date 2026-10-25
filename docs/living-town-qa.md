# Living-town verification — 2026-10-24

Engine `last-warning-ca/1.4.0`, world `riverside-organic/1`, daily recording `riverside-life/1`. The production TypeScript/Vite build passes. The complete backend suite passed **196 tests**; all backend application and test files pass Ruff. After minor existing test lint fixes, the 28 affected tests passed again. Unrelated launcher/worker script lint findings are unchanged. Vite retains its advisory about the Pixi engine chunk exceeding 500 kB uncompressed.

## Canonical world and complete day

An independent verifier (`scripts/verify_living_town.py`) checked all 288 frames of the actual 300-resident day, including graph connectivity, every movement edge/fraction, actual indoor occupancy, household homes, co-located conversation participants and a midnight loop without teleporting.

- 446 connected road/path/bridge nodes and 120 river cells; the river center varies from x16 to x22.
- 64 home buildings, 75 households, 4 workplaces, 2 schools, 2 civic buildings, 3 shops, 3 parks and 8 actual refuge buildings.
- 22,354 recorded motion paths, including 6,783 turning paths.
- 2,920 co-location interaction observations across the day. A continuing meeting can produce multiple observations; this is not 2,920 unique social relationships or generated conversations.
- 08:00: 70 residents indoors and 230 outside. Noon: 34 indoors and 266 outside. By 23:00, all 300 are indoors; the final day positions match midnight.
- Generation took 1.28 seconds in the direct check; first HTTP preview took 2.34 seconds. Browser responses support gzip and the cache is bounded to four worlds. A separate 1,000-resident generation completed in 2.43 seconds with a 4.11 MB gzipped result.

The schedules and interactions are local simulation data. No model calls are used for daily playback. Indoor routing positions remain building entrances; rooms, building damage and home protection are not simulated.

## Three-disaster local integration

Both warnings completed for each disaster using the explicit **Rules baseline**, 300 residents, seed 42, visible daily tick 96 (08:00), 120 emergency ticks and zero neural coupling. These are rules outcomes, not Bedrock results.

| Disaster | Sheltered, generic / actionable | Exposed, generic / actionable | Real Mini shapes |
|---|---:|---:|---|
| Flood | 149 / 234 | 83 / 35 | 5 × 20,484 / 8 × 20,484 |
| Wildfire | 68 / 178 | 96 / 53 | 5 × 20,484 / 10 × 20,484 |
| Tornado | 50 / 170 | 46 / 24 | 5 × 20,484 / 11 × 20,484 |

Every pair had matching initial-condition hashes and identical physical hazards/closures. Emergency frame zero matched the visible town's positions exactly. Duplicate job submissions returned the same job. The cached day was unchanged after all experiments. All six Mini artifacts were reused only after exact warning/stimulus hashes, model/source revisions, protocol, dimensions, finite nonconstant values and time axes were checked. Evidence: `output/living-town-rules-e2e.json` (`verified: true`).

## Renderer checks

Browser checks verified upright building facades, actual path geometry, day/night lighting, real conversation bubbles, occupied-building selection and household inspection. At midnight there were 300 indoor residents, zero outdoor sprites and 64 occupied homes. Repeated clicks on one occupied home selected actual occupants 0 then 1. An actual four-vertex arrival for resident 50 remained visible at interpolation fraction 0.99 and hid only at 1.0.

Screenshots are in `output/playwright/living-town-*.png`. Rendering uses recorded time, activity and paths; it never invents route links or model decisions. Browser viewport checks do not establish physical mobile-device or Safari performance.

The production UI submitted a real 300-resident Rules warning from 22:00 (tick 264), completed it with the exact-text real Mini artifact, and returned to the same daily tick. All 300 initial positions and profiles matched the visible day snapshot. Run `347b9a50-cc29-4e3b-b451-c007b94f4f92` incurred zero model calls. Return cleared the replay strip and pending-job storage. Evidence: `output/living-town-ui-qa.json`.

An old grid recording also played to its original 120-tick endpoint, then returned to organic daily life. The final production browser reported zero console errors and warnings. The current production screenshot is `output/playwright/living-town-final.png`.

Final 390- and 320-pixel production viewport checks passed after correcting an inspector/camera/clock overlap. At 320 px, the expanded daily inspector ends at y471, camera controls occupy y486–534, and the town dock begins at y564. During replay, those bounds are y413, y421–469 and y497. Camera hit testing succeeds, town controls remain 44 px tall, and document width equals viewport width. These are desktop-browser responsive checks, not tests on physical phones.

## Actual Bedrock emergency decisions

Both flood warnings completed with 300 residents at daily tick 96, real Amazon Nova Micro requests and the existing exact-text real Mini artifacts. Protocol `nova_resident_json_life_v1` supplied actual household, workplace, activity and occupancy context. The model produced real `CONTINUE_ROUTINE` and `EVACUATE` choices. The physical engine remained authoritative for travel and hazards.

| Warning | Sheltered | Exposed | Model requests | Recorded choices | Accounted cost |
|---|---:|---:|---:|---:|---:|
| Generic | 6 | 258 | 120 | 1,198 | $0.028867020 |
| Actionable | 167 | 119 | 103 | 1,013 | $0.024460135 |

Run IDs: `0403e22b-5a86-4641-b842-0debdaf7e0f2` and `2f28d726-92fa-4893-99f4-062553d5649a`. The complete-run requests have AWS request evidence and settled usage. Both recordings start at the actual visible daily positions and clock; initial hashes and physical hazard sequences match. Their comparison was saved, and the cached day remained unchanged. Evidence: `output/living-town-bedrock-e2e.json` (`verified: true`). These uncalibrated outcomes demonstrate integration, not measured human behavior. The presets also differ in delivery assumptions, so this is not an isolated wording-only experiment.

A development hot reload reset an additional browser test's draft from Rules to Bedrock before submission. That unintended test was cancelled at the first decision round; 24 completed requests remained honestly accounted and no recording was produced. Subsequent UI testing used the production build and a test-only guard against unintended model submissions.

The two completed runs cost $0.053327155. Including the cancelled test, this verification added $0.058758560. The cumulative application accounting was **$0.381153360**, including 13 retained historical uncertain reservations and the prior smoke estimate. No current verified run has an unsettled reservation. Caps remain $0.30/run, $5 for the Bedrock phase, and $30 for the project. These figures are local accounting and usage estimates, not a verified AWS bill or credit balance. Daily life and Mini added no cloud cost.

## Bounded performance observation

A 30.009-second full-UI daily-play sample recorded 3,610 browser animation-frame samples, with median 8.3 ms, p95 9.2 ms and maximum 17.3 ms intervals. The town advanced from tick 96 to 128 while indoor occupancy changed from 70 to 225. Environment: Chrome 154, 1440 × 900 viewport, DPR 1, ANGLE Metal on Apple M4, one canvas and 300 residents. Other development tasks were active. This is a bounded browser scheduling observation, not a guarantee of rendering performance on all devices or an isolated benchmark.
