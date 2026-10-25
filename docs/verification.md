# Executed verification — 2026-10-24

This is the historical integration report for the earlier city and engine. The current organic town, daily-life and warning-handoff checks are in [living-town verification](living-town-qa.md); the preceding pixel-renderer checks are in [pixel-world verification](pixel-world-qa.md). Counts and spending snapshots below are preserved as historical evidence.

## Automated checks

The complete backend suite passes **160 tests in 7.20 seconds**. Unit tests use temporary stores and mocked model boundaries, without paid provider requests or checkpoint downloads. One upstream Starlette warning concerns its deprecated httpx TestClient adapter. Provider tests cover strict JSON decisions, available actions, missing/duplicate IDs, bounded correction/retry, request audit evidence, durable budget reservations and explicit failure; API tests also enforce decision-protocol compatibility for comparisons.

TypeScript checks and the Vite production build passed for the rebuilt workspace. Targeted Ruff checks pass for the simulation, inference tests and end-to-end verifier.

Existing coverage includes deterministic rule recordings, common populations/hazards across warning interventions, rule-mode text edits preserving behavior, legal state transitions, exact population accounting, actual shortest-path movement, shelter arrival, delivery/notice/share timing, warning CRUD, immutable snapshots, replay persistence, comparisons, scenario validation and safe artifact import/export.

Disaster tests exercise real exposure, closures and replanning; wildfire wind bias, river barriers and burnout; tornado movement, city exit, persistent debris and local shelters; and original flood outcome compatibility. Inference tests cover exact-text registration, model/source/protocol/hash-aware cache reuse, missing artifacts, force/recompute, warning edits during a job, strict run binding at zero coupling and unchanged outcomes when neural coupling is off.

The new engine tests verify that model `EVACUATE` decisions bypass zero notice/action probabilities and long rule preparation delays; model `WAIT` never turns into automatic rule evacuation; preparation/sharing hold position until a later model decision; contexts contain actual local perception/routes/neighbors/memory; everyday priorities vary reproducibly and are saved in initial conditions; unwarned residents do not receive an unseen hazard type; invalid/incomplete decisions and provider failures abort explicitly; and model-guided movement still obeys accessible graph edges across all three disasters. These tests validate integration, not the quality of real model responses.

## Real local TRIBE Mini and rule-mode demo

The pinned official Mini checkpoint runs on this MacBook Pro (M4, 16 GB), using Torch 2.6.0, an Apple Metal/MPS brain encoder and CPU Llama 3.2 1B text features. Official source is clean at `af58661791a351a448a489042a28f6c37e1c14b7`; Mini checkpoint revision is `f3463fd77b17d80e4f61636bc2674b375803e743`. Dependencies are pinned in `backend/requirements-tribe-mac.lock`.

Executed `backend/scripts/verify_disasters_demo.py` against the production localhost service. It created three independent verification scenarios without changing interactive Riverside, analyzed both seeded warnings, attached genuine Mini results at zero coupling, ran baseline/alternative simulations, saved comparisons and compared neural arrays. These measured evacuation outcomes are explicitly from the deterministic **rules** mode, before the new Bedrock-agent demonstration.

| Disaster | Generic Mini shape | Actionable Mini shape | Sheltered: generic / actionable | Exposed: generic / actionable |
|---|---|---|---|---|
| Flood | 5 × 20,484 | 8 × 20,484 | 188 / 235 | 29 / 19 |
| Wildfire | 5 × 20,484 | 10 × 20,484 | 87 / 185 | 68 / 50 |
| Tornado | 5 × 20,484 | 11 × 20,484 | 52 / 172 | 33 / 21 |

All six NPZ artifacts were downloaded and independently checked for finite, nonconstant values, metadata-matching shape, strictly increasing times, pinned model/source revisions, real provenance and exact warning/stimulus hashes. Every warning pair shared initial-condition hashes and identical hazard/closure sequences. Each recording had 121 frames, all 300 residents, matching final metrics and actual delivery/shelter-arrival events. Every neural comparison aligned five shared samples.

Actionable wildfire and tornado required new real local Mini execution during this check; four other results used validated existing Mini artifacts. The protocol records controlled reading at 2.5 words/second rather than measured speech. Evidence including all scenario/run/analysis/comparison IDs, artifact checksums and metrics is in ignored `output/e2e-disasters.json` (`verified: true`). This local verification added **$0 cloud inference spending**.

Mean absolute prediction differences were `0.03195787487565028` for flood, `0.03680245196680613` for wildfire and `0.03888095115718892` for tornado. They compare model predictions, not measured brain recordings or established human response effects.

## Executed browser checks

The final production build reopened the saved Bedrock flood comparison through Saved runs, rendered both cities, sought to tick 120 and stepped backward/forward. Bedrock request accounting stayed exactly **692 → 692**, confirming replay made no new inference calls. The final browser session had **zero console errors and zero warnings**. The comparison was also opened in the user's existing in-app browser and left at the completed frame. Final evidence: `output/playwright/final-bedrock-comparison.png`.

On the real 300-resident recording, selecting resident 182 showed the saved `EVACUATE` choice, “Observed flood” reason and tick-32 / 02:40 timestamp. Advanced usage matched 113 requests, 1,107 decisions, 429,110 input / 30,306 output tokens and $0.019262 rounded estimated/accounted cost. A fresh 390 × 844 browser viewport had no horizontal overflow; the final mobile inspector clears camera controls by 11 pixels. Final screenshots are `output/playwright/final-bedrock-300-resident-mobile.png` and `final-bedrock-300-usage-desktop.png`.

The final TypeScript/Vite build and targeted Ruff checks passed. A scan of 71 application/source/documentation files found no AWS access-key or session-token patterns. Credentials for the running local server remain in its process environment, not the application files.

The rebuilt single-workspace React/Three.js simulator was exercised in real Chromium using actual local API data. The synchronized 3D rule-mode flood comparison reached **188 generic / 235 actionable sheltered**, retaining +47 sheltered, −10 exposed and −9 stranded. Playback and seeking read saved frames in both views. Browser evidence is in ignored `output/playwright/` and `.playwright-cli/`.

Earlier real Mini verification also confirmed artifact/metadata downloads and persistence after production-server restart. Historical synthetic upload checks used an isolated temporary QA store, not the normal app data. The seeded library now contains six warnings across three disasters, each with verified genuine Mini output. Saved experiment counts grow during browser QA and new runs.

## Actual Bedrock residents with real Mini results

All six complete 300-resident runs passed live end-to-end verification using actual Bedrock `us.amazon.nova-micro-v1:0` requests in Ohio, decision protocol `nova_resident_json_v4`, engine `last-warning-ca/1.3.0`, and the genuine local Mini artifacts listed above. These are separately measured **Bedrock-mode** outcomes; they are not the rule-mode results relabeled.

| Disaster | Sheltered: generic / actionable | Exposed: generic / actionable | Recorded model choices: generic / actionable |
|---|---|---|---|
| Flood | 54 / 193 | 185 / 84 | 1,107 / 898 |
| Wildfire | 36 / 149 | 102 / 66 | 1,074 / 906 |
| Tornado | 32 / 201 | 33 / 9 | 1,104 / 668 |

Every run included all four decision epochs, individually saved resident actions/reasons, AWS request IDs, context hashes and settled token usage. Each warning pair retained matching initial positions/population, the same physical hazard and road closures, 121 complete replay frames and matching pinned Mini artifacts with both exact warning hashes. Coupling strength was zero: Mini results accompanied the run independently. Simulation comparisons and neural comparisons were saved successfully. Corrective provider requests, where needed, obtained actual missing/eligible model decisions rather than inventing replacements or falling back to rules.

The six completed runs contain **5,757 model decisions** across **592 provider requests**, with **2,260,565 input tokens** and **161,840 output tokens**, estimated from returned usage at **$0.101777375**. Each run stayed below its $0.30 limit. Their usage records have no unsettled reservations. Detailed evidence is in ignored `output/e2e-bedrock-flood.json` and `output/e2e-bedrock-disasters.json`, both `verified: true`. The flood proof also independently downloads and checks the two exact Mini artifacts; the disaster verifier checks the four wildfire/tornado artifacts and stores their checksums.

These results demonstrate working model-driven decisions and independent numerical inference in the simulator. They do not establish calibrated disaster outcomes, human behavioral accuracy, a causal effect from Mini to evacuation, or deterministic reproduction of a new Bedrock generation. The supplied warning presets also differ in physical delivery reach/channels; their outcome difference is not an isolated wording-only experiment.

## Cloud history and limits

Earlier EC2 GPU attempts in Ohio and Northern Virginia failed on zero On-Demand/Spot quotas; organization policy denied the automatic quota-increase request. Temporary keys/security groups were cleaned up, and both regions were checked for leftover project instances, volumes, groups and keys. No paid EC2 compute/storage started. An earlier real Bedrock Nova Micro smoke request succeeded for an estimated **$0.00000441**. Account billing/credit dashboards were not queried.

The final ledger snapshot is in ignored `output/final-agent-budget.json`. It includes **692 requests**, including failed development/smoke attempts, and returned usage of **2,712,734 input tokens** plus **199,182 output tokens**. The token-based estimate is **$0.12283117**. Conservative project accounting is **$0.17562902**, including the earlier smoke estimate and eleven retained uncertain reservations from old failed requests. Those eleven entries are historical billing uncertainty, not eleven active workers or currently pending jobs. The completed six-run demonstration has settled usage.

The ledger enforces $0.30 per run and $5 for this Bedrock phase within the $30 project ceiling. The snapshot leaves $4.82437539 of the phase allowance. These are local reservations and public-price usage estimates, not an AWS billing statement; the billing/credit dashboard remains unqueried. Local TRIBE adds no cloud cost. Full-size TRIBE CUDA execution, cloud deployment, calibrated disaster physics and scientific validation of neural coupling remain unverified. Prior targeted scans found no supplied credential strings in application/frontend source or documentation.
