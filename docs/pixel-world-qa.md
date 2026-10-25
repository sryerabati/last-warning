# Pixel world release verification

Implemented and verified 24 October 2026 after approval of the transformation plan.
The coverage inventory below defines the controls reviewed; measured evidence and its limits follow it.

## Shared coverage inventory

| Claim / control | Functional check | Visual evidence / state |
| --- | --- | --- |
| One full-screen game workspace | World, essential HUD and replay controls fit viewport; no page overflow | Initial desktop and 390×844 layout captures |
| Original detailed pixel city | Real roads, river, bridges and shelters align; stable seed | Neighborhood and overview, native and detail zoom |
| Real residents | All recorded IDs retained, picking opens actual state and reason | Crowded bridge and selected Bedrock resident |
| Faithful movement | New motion paths use recorded road edges; ambiguous old transitions snap | Walking replay around a corner; seek and restart |
| Flood, fire and tornado | Select each scenario; active/affected sets and closures match | Each disaster before/active/aftermath |
| Run warning | Two real warnings complete through background jobs; actual progress and Mini attachment | Running, completed and failure states |
| Comparison | Same initial hash; synchronized playback and camera; real outcome delta | Paired 300+300 residents |
| Warning editor | Edit, save, switch presets; preserve original recorded text | Long text, channels and selection |
| Resident inspector | True details and recorded route only; close/reselect works | Occlusion and overlapping residents |
| Camera | Pan, zoom in/out/reset; keyboard access; resident selection unaffected | Detail/overview and clipped-edge cases |
| Replay | Play/pause, step, seek, speed, restart; paused effects freeze | Early/end frames, backwards seek and active hazard |
| History and Advanced | Saved run loads correct warning/scenario/analysis; all tools accessible | Library, settings, metrics and methods |
| Real TRIBE Mini | Exact text hashes, pinned model/revision, nonconstant 20,484-vertex artifact | Neural panel and comparison |
| Sound | Explicit enable, mute, pause/resume; no autoplay errors | Toggle focus and muted default |
| Idempotence / cancel | Duplicate job key schedules once; cancel preserves incurred accounting | Actual terminal job state and concise UI feedback |
| Accessibility | Tab/focus/Escape, readable text, labels, reduced motion | Focused dock, open panel and mobile bottom sheet |
| Production | TypeScript/build passes; backend suite passes; no runtime/asset errors | Browser console and network checks |
| Performance | Measure actual frame intervals in single/paired view; report machine/backend | Recorded run, zoom/pan, 60-second sample |

## Exploratory cases

1. Switch disaster while inspecting a resident or an old run; the map, warning, metrics and selected person must not mix unrelated contexts.
2. Seek backwards during a hazard, close/reopen panels, then reload; saved selection and run loading must remain consistent without duplicate paid jobs.
3. Change a warning while a run is queued; the run uses its immutable request snapshot or reports a clear conflict. Mini predictions must never attach to different text.
4. Disable sound or pause during an active effect; no continued visual ticker or unexpected audio should remain.

## Evidence

### Build and functional checks

- Final production TypeScript + Vite build passed. The only build advisory is the 576 KB Pixi chunk (168 KB gzip).
- Backend suite: **175 tests passed**, including recorded movement/routes, background job idempotency/cancellation/recovery, budget reservations and serialized Bedrock client/network access. Changed Python files pass Ruff; unrelated pre-existing whole-repository lint findings were not changed.
- The final production workspace passed desktop and **320×844 / 390×844** browser viewport checks: no horizontal page overflow, all three outcome counts readable, warning dialog focus contained, Escape returns focus, real Mini chart visible, zero console errors/warnings. These are browser viewport checks rather than physical-device tests.
- Real resident picking, overlapping selection, follow, pan/zoom, pause/seek/restart, shared comparison camera and recorded-route toggle were exercised. Legacy recordings have no invented routes. Twenty alternating single/paired renderer lifecycle cycles and WebGL context recovery passed the bounded renderer checks.
- Sound starts muted. Explicit enable/mute and replay play/pause passed without autoplay/runtime errors. Auditory quality was not assessed automatically.

### Real inference and end-to-end results

[Six-run report](../output/pixel-world-e2e-bedrock-resumed.json) verifies both warnings for every disaster with actual Bedrock decisions and exact-text local Mini artifacts:

| Disaster | Generic sheltered | Actionable sheltered |
| --- | ---: | ---: |
| Flood | 45 | 185 |
| Wildfire | 36 | 148 |
| Tornado | 30 | 201 |

Each pair has 300 residents, 121 frames, matching starting conditions and physical hazard progression, validated road-edge movement, actual resident details and a working saved comparison. Mini NPZ predictions are finite, nonconstant time × 20,484 arrays from the pinned real model/code, matched by exact warning text hash. These are outcomes of the saved runs, not a guarantee about future LLM responses or real human behavior. Neural coupling remained zero; brain predictions were displayed and compared rather than presented as validated causal behavior.

[UI end-to-end report](../output/pixel-ui-e2e.json) records a further actual **Run warning** click, real progress, page refresh during inference, reconnect to the same job ID, and automatic completion/replay. That run sheltered **193/300**, with four real decision rounds, 92 provider calls, 898 decisions, and a matching **8×20,484** Mini artifact. The session reconnect state cleared after completion. No duplicate paid job was submitted on refresh.

A native TLS failure interrupted the first verification attempt. The original failed report is preserved at `output/pixel-world-e2e-bedrock.json`. Explicit boto3 sessions plus a shared one-request concurrency guard fixed the observed crash; the six completed checks and final UI job then passed. The completed first flood recording was explicitly reused rather than billed again.

### Performance and spending

[Accepted frame sample](../output/pixel-performance.json): one visible canvas, two recorded worlds, **600 residents**, 1440×900 on Apple M4/Chrome 154; **60.02 FPS** over 60 seconds, p95 frame interval **16.8 ms**. All 3,601 samples had active animation. An idle sample was excluded. This is one desktop replay measurement, not a complete all-hazard, Safari or physical-mobile benchmark.

After verification, application-accounted project spending was **$0.303895095**, including 13 retained uncertain/pending request allowances, below the **$30** project cap. The final UI run accounted for $0.016034795. AWS billing/remaining credit has not been independently verified. Local Mini and saved replays require no AWS inference charges.

### Evidence files

- [Production mobile report](../output/pixel-mobile-qa.json)
- [Renderer checks](../output/playwright/pixel-renderer-verification.json)
- [Desktop replay](../output/playwright/pixel-final-live-replay.png)
- [Recorded route](../output/playwright/pixel-city-actual-recorded-route.png)
- [Live inference progress](../output/playwright/pixel-live-job-progress.png)
- [320px production](../output/playwright/pixel-production-320-final.png), [390px production](../output/playwright/pixel-production-390-final.png)

Existing pre-redesign reports remain historical. The implementation keeps the canonical simulation geometry and physics; organic map generation, resident routines and expanded city mechanics remain the separately scoped second release in the transformation plan.
