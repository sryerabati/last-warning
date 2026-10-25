# Pixel-art storm demo

The simulator now uses stepped pixel geometry for trees, roads, roofs, shadows, selection rings, weather effects, and control handles. Building names and the readable pixel digits remain intact. Terrain and effects change their appearance only; they do not alter the mapped routes or physical hazard footprint.

## The two recordings

These recordings, IDs, archives, and screenshots describe the local development demo. Runtime data is not included in the public repository; a fresh checkout must generate its own runs and neural analyses.

Open **Runs** in the simulator. The prepared pair uses the same 500 synthetic residents, seed 42, campus, teaching-day schedule, buses, and destructive thunderstorm, starting at 12:30.

- **01 · Late, limited advisory**: the message arrives five simulated minutes after the start, through mobile delivery reaching 30% of residents. It gives general caution rather than clear shelter instructions.
- **02 · Early shelter warning**: immediate broadcast, full configured reach, mobile/siren/social channels, and explicit instructions to enter a substantial building and remain sheltered.

This compares complete warning strategies: wording, timing, and reach differ. It is not an experiment isolating wording alone. Residents use real Bedrock decisions; both warnings have fresh real local TRIBE Mini analyses. Neural coupling is off, so the brain prediction is not presented as the cause of evacuation behavior.

## Verified outcomes

| Recorded strategy | Sheltered at the end | Ever exposed | Never exposed |
|---|---:|---:|---:|
| Early shelter warning | 482 | 64 | 436 |
| Late, limited advisory | 454 | 293 | 207 |

The early warning strategy produced **229 fewer exposed residents (78% fewer)** in this matched pair. Both recordings completed six Bedrock decision rounds with 3,000 accepted choices each. This is a synthetic demonstration, not a population-level efficacy estimate.

The new pair cost **$0.15113** in the application ledger; recorded project spending is **$0.67983**. The ledger is not an AWS billing reconciliation.

For a strong later comparison shot, jump to **20:00**: the late advisory has 430 sheltered / 231 ever exposed, versus 484 sheltered / 55 ever exposed for the early warning. Rain, hail, and wind are still active. At **30:00**, exposure has reached the final 293 versus 64 while the storm is still visible.

## Suggested recording sequence

1. Use a wide viewport, ideally 1600 × 1000 or larger. Keep **Focus the Oval** as the main camera framing.
2. Open the late-advisory run first. Show the opening ordinary campus briefly, then move to **02:00–06:00** for rain, lightning, hail, and residents caught outdoors. Use **4×** for movement detail or **8×** for a shorter establishing shot.
3. Select an exposed resident to show their saved action and exposure time. Close the inspector for the wide weather shot.
4. Open the early-warning run, restart, and show people heading inside before the storm. Use the same time window and camera for the comparison.
5. Open the saved comparison for a synchronized split view. Each side shows its own sheltered and ever-exposed counts.
6. Open **View real Mini response** for a short look at the actual neural prediction, then return to the map.

The full recordings span one simulated hour to include the lightning shelter hold and all-clear. You do not need to record the full hour. Pause before changing runs or dragging the timeline. Sound is on by default after the first click or keypress and follows playback. The simulator remembers an explicit mute preference; check More → Sound when recording with system audio.

“Ever exposed” means contact with modeled hazardous conditions. It is not a count of deaths or injuries. Some affected residents eventually reach shelter, so the sheltered and ever-exposed totals can overlap.

## Archive and verification

The prior 56 runs, 13 analyses, 21 comparisons, and 12 stimuli were removed from the visible history after a verified SQLite backup and artifact copy. They remain recoverable in `data/archives/20261025T075942.920396Z-before-video-demo/`. Warning presets, scenarios, job idempotency, and the Bedrock spending ledger were preserved.

The pixel-art changes passed 105 frontend checks, the production build, and separate static/dynamic visual audits. The final recording IDs, measured outcomes, matching starting-condition hashes, and costs are saved in `output/video-demo-pair.json`.

Production browser verification covered both recordings, synchronized comparison at 20:00, playback/pause, timeline seeking, square slider geometry, art revision 3, and the linked real Mini result. The visible history contains exactly two runs, two analyses, and their one comparison. The in-app browser is left on the late-advisory run paused at 20:00.

Screenshots: `output/playwright/video-demo-good.png`, `output/playwright/video-demo-comparison.png`, and `output/playwright/video-demo-ready.png`.

Recording IDs: late `3a97ecb8-be1e-4884-97a3-ae47cdd9152a`; early `883fdf8d-8854-480b-b4be-442a0b078589`. Comparison `eeb9d1f2-36eb-41a0-ab60-393b7679b2d7`.
