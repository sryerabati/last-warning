# Ohio State campus edition

Visual thesis: an original shaded pixel diorama of Ohio State and the neighboring University District, with recognizable geography, readable residents, and a compact game interface. Content order: world and people, current warning, event selection and playback, then detailed methods and model provenance in the existing drawers. Motion follows the recording: walking, boarding, driving, alighting, conversations, weather, and the daily clock. Reduced-motion preferences stop autoplay.

## Implemented

- Pinned OpenStreetMap exterior geometry for the academic core, South Campus and University District residential blocks, at a stable metric scale in a 68-unit world. Separate walking and directed driving networks retain metre-based edge lengths; cars transfer through authored parking locations. OSM source files, exact query, hash and ODbL attribution are bundled in `backend/app/data`.
- Persistent synthetic students, graduate students, professors, staff and neighbors, with just two local preschool families. Each has a home, household, itinerary, contacts and a saved appearance recipe. Caregivers coordinate shared motion with preschool children while employed parents keep independent schedules; roommates and friends meet at actual nearby positions. Outdoor destinations are distributed across campus paths.
- Original option-C-inspired 32×48 modular character artwork: independent body, skin, hairstyle, hair color, clothing, accessories and headwear; adult/child/older and wheelchair presentation; four facings and eight poses. Shared cached atlases hold many generated combinations. Portraits use the same recipe. Tiny family display offsets separate oversized sprites without changing recorded positions, routing or exposure.
- Actual cars with capacity, boarding, occupants, driving, parking and alighting. Passengers disappear from the pedestrian layer only during their recorded ride. Replay and picking use the same transitions. No moving decorative traffic substitutes for simulated vehicles.
- Seven campus hazards: flood, wildfire, tornado, blizzard, hailstorm, destructive thunderstorm and an abstract major public safety threat. Weather durations use simulated seconds. Storms include last-thunder shelter-hold timing; public-safety instructions expand the avoidance area and issue an explicit simulated all-clear. Local simulation controls routes, capacities and physical state; Bedrock controls high-level resident intentions.
- Fourteen campus warnings with paired delivery/channel/timing parameters. Existing Riverside warnings and recordings are preserved. The campus seed migration is additive and runs automatically.
- One simulator page with an event dropdown, readable pixel numerals, a family/routine inspector, map attribution, weather conditions, replay, comparisons and neural results in drawers.

## Evidence and limits

The implementation uses real geography and source-informed hazard definitions. Households, attendance, trips, parking capacity, protective building properties and weather fields are authored educational assumptions. Named buildings are not asserted to be official emergency shelters. The entire university, bus operations, signal timing, turn restrictions, calibrated flood/wind damage and observed campus behavior are outside this slice. Wheelchair routing avoids known steps but does not establish verified accessibility.

The saved KCMH historical weather sample remains research material. It has not been turned into a calibrated OSU weather reconstruction. Exposure measures modeled contact time, not injury or casualty probability. Mini predicts cortical fMRI response to text; it does not determine compliance or Bedrock decisions.

## Verification

The current audit and fixes are documented in [campus-audit-and-fixes.md](campus-audit-and-fixes.md), including the full behavior, geography and visual findings. Current machine-readable results live in `output/campus-population-audit.json` and `output/campus-car-behavior-audit.json`.

### Current expanded-district milestone

- **255 backend tests passed**, with successful Ruff and production TypeScript/Vite checks.
- Default day: **300 residents, 105 homes, two families, 31 owned cars and 26 daily car trips**. No unreachable residents; no stationary walking labels; peak two-minute sample of 13 park waiters and 69 walkers. All 351 meal/snack/coffee stops use mapped service evidence.
- Desktop/mobile camera checks include bounded map edges, a highlighted house/entrance, inspector-aware framing and unobstructed mobile address exploration. Pixel numerals remain unchanged.
- Real current-world integration: **verified true** in `output/campus-district-v21-bedrock-mini-e2e.json`. Two matched warnings, 40 residents, four owned cars and 121 frames each; Bedrock produced 240 decisions per warning. Genuine matching local Mini artifacts were reused, not regenerated, and their provenance/hashes were checked.
- Saved comparison: `ae38c792-0def-4b2b-8343-fd518e5cd4b7`. Additional final-pair cost **$0.011304615**; tracked project total **$0.415094295**, not independently verified AWS billing.

### Earlier academic-core milestone (retained historical evidence)

- Backend: **235 tests passed**, covering campus world, daily life, emergency behavior, API persistence and comparisons, plus the existing legacy regression suite. The production frontend build and Ruff checks pass.
- Character replay: 300 unique seeded recipes; 414 sampled transition checks across 69 real commute frames conserved every person across pedestrian, indoor and vehicle presentation.
- Day: 720 two-minute frames, 300 residents, 70 cars; all return home by the loop boundary. Latest measured generation approximately 10 seconds and gzip size 8.6 MB. Two cached population/seed days prevent unbounded preview growth.
- Browser: desktop and 320-pixel mobile viewport; event menu, inspector, household navigation, clock, camera and saved replay.
- Real model integration: **verified true** in `output/campus-bedrock-mini-e2e.json`. Two matched severe-thunderstorm warnings, 40 residents and 9 cars, 121 frames each. Bedrock supplied 240 decisions per warning; real local Mini artifacts have shapes 7×20,484 and 18×20,484. Both share initial conditions and are available as a saved comparison. Additional accounted Bedrock cost: **$0.01118628**; project ledger after verification: **$0.39233964**. This ledger is application accounting, not a verified AWS billing statement.
- Blizzard, hail and public-safety visual replays were created with the explicit local Rules baseline, without paid inference. Their IDs are in `output/campus-weather-visual-runs.json`. They must not be described as Bedrock results.

Run the explicit final integration check with `python scripts/verify_campus_demo.py --bedrock`; this makes paid requests under the existing application caps. Without `--bedrock`, resident decisions use the explicit local rules baseline. Both modes require genuine local Mini results for the two warning texts. Reuse the same `--output` with `--resume` to reconnect; failed paid jobs are never replaced automatically.
