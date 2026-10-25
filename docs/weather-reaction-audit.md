# Weather reactions: implementation and audit

Verified October 25, 2026. Engine `last-warning-campus/3.1`; daily-life cache `osu-campus-life/3.1`.

## Implemented

- Residents who choose urgent shelter travel now physically hurry, with matching procedural running poses. Children, older residents, wheelchair users, and groups retain constrained paces. Snow uses shorter, careful steps instead of running.
- Animation follows recorded speed and motion. A stopped pedestrian stops stepping; pause and seek preserve the recorded pose. The inspector distinguishes current pace from usual walking pace and explains weather responses.
- Snow changes vehicle speed, acceleration, braking, and following distance. Walking and driving have different factors. Accumulated snow continues to affect travel after precipitation ends.
- Cars and buses show headlights, wipers, brake/hazard lights, roof snow, wet spray, and short tracks along their actual recorded path.
- Tornado ground contact creates recorded resident/vehicle impact episodes. Pedestrians brace or fall and recover; wheelchair users brace upright. Vehicles stop and visibly rock within a bounded pose. Impacts do not invent model decisions or teleport travelers.
- Bus boarding, alighting, and dwell progression pause during impact and recovery, including empty buses. Route estimates account for weather across walking, driving, and transit transfers.

## Audit fixes

Three subagents separately implemented and cross-reviewed resident presentation, vehicle presentation, and physical behavior. The audit fixed:

1. Endpoint activity states leaking backward into interpolated replay.
2. Walking animations continuing after arrival or snapping on pause.
3. Ordinary snow/hail exposure freezing moving pedestrians.
4. Stale nonzero speeds on parked or held vehicles.
5. Bus transfers continuing during tornado impacts.
6. Old impact metadata surviving after recovery.
7. An alighting edge case restoring a parked car to a yielding state.
8. Travel estimates ignoring weather effects on some route legs.

## Verification

- Full backend suite: **326 passed**. One existing Starlette/httpx deprecation warning.
- Frontend verification scripts: **102 passed**. Production TypeScript/Vite build passed; existing large Pixi bundle warning remains.
- Three complete offline engine audits, each with 300 residents and 121 frames: thunderstorm, four-hour blizzard, and tornado. No stranded residents in those seeded scenarios. Checked finite speeds, constrained resident paces, stopped vehicle speeds, passenger capacity, and exact rider/vehicle positions.
- Thunderstorm and tornado audits each recorded 55 residents running at some point. Blizzard recorded careful movement and six snow-affected vehicles. The snow-driving browser case occurs after precipitation has ended, verifying persistent surface effects.
- A separately labeled controlled fixture places a pedestrian, car, and empty bus in a tornado path. Their contact and recovery are computed by the actual engine. This fixture tests contact presentation; it is not a naturally occurring live-model outcome or measured human behavior.
- Browser checks use the actual Pixi renderer, recorded movement, and production UI. Running, careful steps, snowy driving, vehicle stopping, and tornado contact/recovery were inspected.
- Controlled browser replay confirmed a visible fallen pose at 33 seconds and an upright recovered pose at 88 seconds. Re-rendering a paused frame produced byte-identical canvas screenshots.

### Live model check

Saved run `2b9172d5-3a7c-4777-a72e-8609de390e3c` is available under **Runs → Tornado shelter warning**, October 25, 3:46 AM.

- 80 residents; six Bedrock decision rounds; 480 accepted choices; 121 saved frames.
- Model: `us.amazon.nova-micro-v1:0` in `us-east-2`.
- 49 calls, including one successful validation retry. No fallback decisions were invented.
- Existing real TRIBE Mini analysis reused: `c352fef5-4e43-4391-91ec-901fb5aaa8c5`. Coupling remained zero; this check did not rerun TRIBE inference.
- Arlo Foster visibly runs to shelter at approximately 2.2 m/s after the recorded 00:10 decision. No tornado contact occurred in this live run; contact is covered by the controlled fixture and backend tests.
- This verification added **$0.012258365** to the application ledger. Recorded project total is **$0.52869824**, below the $30 cap. These are application token-cost records, not an AWS billing reconciliation.

Evidence: `output/weather-behavior-e2e.json`, `output/weather-live-e2e.json`, `output/weather-live-recording.json`, and screenshots under `output/playwright/weather-reaction-*`.

## Evidence and limits

[NHTSA winter-driving guidance](https://www.nhtsa.gov/winter-driving-tips) supports slower travel and increased following distance. [FHWA road-weather effects](https://ops.fhwa.dot.gov/weather/roadimpact.htm) support modeling effects on speed and traffic flow, but its roadway statistics do not calibrate individual campus travelers. [National Weather Service tornado guidance](https://www.weather.gov/safety/tornado-during) supports seeking substantial shelter and treating vehicles as unsafe shelter. [NWS winter guidance](https://www.weather.gov/safety/winter-during) supports cautious movement during winter conditions.

Pace multipliers, traction factors, and the eight-second vehicle recovery interval are authored educational parameters. This is not a calibrated prediction of Ohio State pedestrian behavior or an injury model. Weather-aware route estimates still omit live traffic queues. Snow is currently a shared surface condition, not a plow-by-plow road model.

## Highest-value next improvements

1. **A searchable event timeline.** Jump directly from warning receipt, shelter departure, impact, or delay to the relevant person and time. Record a plain-language reason for every stop. This makes outcomes understandable without hunting around the map.
2. **Physical shelter entrance queues.** Capacity reservations exist, but doorway entry needs throughput, accessible entrances, group admission, and visible waiting lines. This would reveal bottlenecks that instant admission hides.
3. **A better warning comparison scorecard.** Separate people already indoors from people newly protected by a warning. Compare time to safety, outdoor exposure seconds, delayed trips, and unmet shelter demand across repeated seeds.
4. **Route-specific snow clearing and recovery.** Track cleared paths, blocked roads, debris removal, and accessible routes. Let residents and buses replan as conditions improve instead of applying one broad weather factor indefinitely.

Start with the event timeline, then shelter queues: they improve both the simulation's usefulness and the player's ability to understand it.
