# Campus emergency runtime

The campus path is selected by `ScenarioConfig.layout = "campus"`. It uses the pinned campus walking/driving world and `CampusLife` for every movement, household, boarding, parking, indoor admission, and daily agenda. Existing grid and organic recordings still use their existing engine.

## Decision boundary

Bedrock uses the versioned `nova_resident_json_campus_v3` protocol and the existing Nova Micro Converse client, strict response parser, durable budget reservations, and caps. No additional provider is required. Five base decision opportunities occur at 10, 40, 120, 280 and 480 simulated seconds after the warning is scheduled. Locally observed danger may start that bounded schedule earlier. Delivered public-safety perimeter updates and an explicit scenario-authority all-clear also trigger a decision round. Recording frame duration does not change these opportunities. The provider receives exact elapsed seconds and a containing frame index; the index is not a response delay.

The model gets the resident's actual position, current activity, household, travel leader, warning receipt, delivered update, locally observed danger, feasible destination, and last three decisions. Undelivered warning text and the hidden future hazard field are excluded. Choices are validated for every resident before any are applied. Provider failures or invalid choices fail the job; there is no rules fallback. The separately selected rules mode never calls or attributes results to a model.

Each campus request begins with an explicit per-resident action menu. If a structurally valid response contains invalid or missing resident choices, the parser collects all affected IDs and retains only the other fully validated model choices. One repair request asks the model to decide only the unresolved residents. It cannot revise already accepted residents. Duplicate/unrequested IDs or malformed envelopes are not salvaged. There are still at most two provider attempts per batch, all billed attempts are accounted, and the whole decision round remains unapplied until every choice validates. A failed repair stops the job rather than inventing an action.

This fixes the observed blizzard failure in request `962d7613-8837-4547-9849-2707e2fa80b4`: the first response chose `CONTINUE_ROUTINE` for dependent residents 2 and 5. The old whole-batch retry fixed those dependents but changed previously valid, unalerted resident 1 to an unavailable `SHARE`. The regression fixture reproduces the first response and verifies that only IDs 2 and 5 are sent for repair, while resident 1's actual first choice remains intact.

Supported campus intentions include `SEEK_INDOOR_SHELTER`, `SHELTER_IN_PLACE`, `POSTPONE_TRAVEL`, `EVACUATE_AREA`, `CONTINUE_ROUTINE`, `WAIT`, `PREPARE`, `SHARE`, and `STAY_WITH_GROUP`. Only the designated household travel leader controls a shared trip. Dependents explicitly choose to stay with that group or share information. They are not offered a misleading `WAIT` that cannot stop their vehicle. A leader's `WAIT` holds the actual position and does not invent parking. `POSTPONE_TRAVEL` is unavailable while boarding or aboard a car.

Shelter candidates must have an eligible authored building type, enough currently occupied plus reserved capacity for the complete household, and an executable route. Candidates are ranked by feasible movement time: graph distance at the unit's walking speed, or driving plus walking time through a legal parking transfer. Straight-line distance is only a lower bound that prunes destinations that cannot improve the current choice. This is a route-ranking cost, not a traffic ETA; it excludes dwell and the common scenario speed multiplier. If an earlier action consumes a destination's available capacity, the later action becomes an explicit unmet need; the engine does not substitute an unchosen target. Admission rechecks occupancy. Cars keep their occupants until actual parking and alighting transitions.

## Time, hazards, and information

The generic siren channel is modeled as an outdoor tone cue, with authored reach rather than measured acoustics. It records `siren_heard` separately from delivered/noticed warning text and reaches only outdoor, in-scene residents at delivery time. A tone can motivate shelter consideration; it does not disclose warning text, hazard identity, or the global shelter-hold countdown, and does not enable sharing an unseen message. A later mobile or social message still delivers normally. The deterministic baseline also responds to the cue, independently of visual hazard observation. Franklin County's real system can use tones or spoken messages; spoken payloads are not represented by this generic tone-only channel. See the [behavior fidelity audit](research/behavior-fidelity-audit.md) for sources and remaining limitations.

Campus coordinates are continuous within the serialized `map_bounds`. Graph edge lengths and movement speeds use meters. `town_start_minutes` freezes an exact moment from the ordinary-day recording; the legacy `town_start_tick × 5` convention remains a fallback.

Default 120-frame scenarios span four hours for blizzards, one hour for hail and destructive thunderstorms, twenty minutes for the generic public-safety exercise, and ten minutes for the existing hazards. A shorter-than-three-hour blizzard or shorter-than-one-hour hail/thunderstorm scenario is rejected.

Blizzard criteria are the inclusive Wilmington thresholds: wind at least 35 mph, falling/blowing snow, visibility no greater than one quarter mile, and at least three qualifying hours. The deterministic authored blizzard profile lasts 3.5 hours, followed by recovery. Thunder reports occur every two minutes during the authored storm; the all-clear follows at least thirty simulated minutes after the final thunder. These are simulation seconds, independent of browser playback speed.

Public safety is a fictional danger/avoidance area with a generic perimeter update at five minutes and an explicit all-clear at fifteen minutes. It contains no incident actors or specified cause. Closures forbid new entry. A special directional egress score permits routes that monotonically leave this generic zone. Flood and fire closures remain conservative; they do not gain traversability from the egress exception. Tornado debris persists in the recorded closure field.

Indoors is not universally safe: flooding/fire proximity can invalidate an indoor destination. A doorway, park, or car is not counted as a substantial building. Shelter types and capacities are authored assumptions, not official campus shelter certifications.

## Recording and outcomes

Campus recordings use `last-warning-recording/3`, `last-warning-campus/1` art, and `osu-campus-life/1` daily life. Standard agent rows and the existing eight state names are retained; vehicle, activity-transition, and motion fields extend the recording. Frames are JSON roundtrip compatible.

`sheltered` is current eligible indoor occupancy, including people who were already inside. `exposed` is the cumulative count with some hazard contact. The exposure duration integrates actual indoor/outdoor transitions and solves swept relative-motion intersections against the authored ground footprint. A canonical one-second internal clock is independent of recording frame duration. Flood/fire indoor suitability is checked at that bounded internal interval. It is not an injury or death probability. After the all-clear, residents who resume routines can leave buildings, so the final sheltered count is not a cumulative success score.

The underlying weather profiles, response probabilities, schedules, travel reductions, hazard footprints and alert timing are authored educational assumptions. The research source definitions and pinned campus geography are evidence; this runtime is not an OSU forecast or a fit to measured resident behavior. TRIBE results remain a separate neural-model artifact and do not become measured compliance or harm.

## Verification

`backend/tests/test_campus_emergencies.py` checks all seven hazards, compound thresholds and missing values, lightning reset/hold timing, hazard-specific indoor protection, exact frozen-minute initialization, household authority, capacity reservation, actual route-cost selection, siren/message information separation, strict campus protocol parsing, no silent model fallback, public-safety update memory, and JSON replay. `backend/tests/test_bedrock.py` includes the observed blizzard-response regression, subset repair, strict envelope ownership, retry limits, and billing conservation. Main provider tests use local doubles and spend no credits. Additional existing Bedrock, legacy simulation, living-town, and motion tests cover regression behavior.

A local 300-person, 121-frame destructive-thunderstorm baseline completed in approximately 4.3 seconds on the development Mac, starting with 184 people outdoors and 70 vehicles. This is a development observation, not a performance guarantee.

### 2026-10-25 repair verification

The full backend suite passed: **275 tests**. A separate 300-resident, 121-frame thunderstorm run completed with the revised route selection and cue semantics. Ruff passed for all changed Python files.

A real Nova Micro run through the existing authenticated local server completed on protocol `nova_resident_json_campus_v2`: run `59a54296-c98f-4116-aaae-26d0475edb96`, 10 residents, 13 recorded frames, two decision rounds and 20 model-authored choices. Both provider calls settled without validation errors. Usage was 10,300 input tokens and 625 output tokens, accounting for **$0.000448** incremental spend; the ledger increased from $0.41566014 to $0.41610814. The scenario was bounded to at most four attempts, whose conservative combined reservation is $0.0196. This is the application's priced usage ledger, not an AWS billing reconciliation.

The smoke run exercises live inference; the stored-response regression specifically exercises the observed blizzard repair path without paying to force another invalid output. Machine-readable evidence is saved in `data/bedrock-campus-v2-smoke-test.json`, alongside the replay recording. No credentials were extracted or persisted, and no server restart was required.

## Response timing and visible contact — engine 3.0

New campus runs use explicit `broadcast_seconds` and `preparation_seconds`. If absent, legacy warning fields convert using the historical five-second reference, so a blizzard's 120-second recording interval does not multiply human delays. Stored older recordings retain their original semantics. Authored seeded delays are 5–15 seconds for mobile receipt, 5–20 seconds for attention, five seconds for siren/social delivery, and 2–7 seconds after local hazard observation. These values define a reproducible teaching scenario; they are not measured OSU response distributions. Bedrock decisions remain bounded to five base opportunities plus the existing authority-update rounds.

The life engine accumulates complete paths and activity changes while integrating in one-second steps. Messages, decisions, starts and arrivals carry physical seconds. Output frames merely sample the result. Exact event timestamps appear alongside `tick` in replay metadata, with `agent_policy.decision_times_seconds` and per-choice `time_seconds`.

Tornado contact is evaluated against the moving 1.8-unit ground footprint, not the tall decorative canopy. An analytic relative-motion sweep catches contact between safe frame endpoints. `hazard_motion` records the center path, normalized fractions and the active portion of a frame. `agent_impacts` records contact start/end and recovery, including an entire episode that begins and ends within one coarse frame. On-foot tornado contact triggers a temporary authored knockdown/recovery; occupied vehicles brace and stop temporarily. Routes and chosen intentions remain preserved, and the reaction does not label anyone injured or dead. Other physical hazard contacts can show a bracing cue; the abstract public-safety zone does not apply physical force.

A tornado warning suspends bus boarding through the transit controller; buses discharge at a reachable stop and wait. The scenario authority's all-clear resumes service. Resident model decisions never eject passengers onto a road.

`backend/tests/test_campus_response_timing.py` verifies complete message/action events, outcomes and final positions across 5-, 10- and 25-second recordings; bounded model rounds and explicit provider clocks; legacy-field reference conversion; swept contact with safe endpoints; sudden perimeter expansion; full tornado contact/recovery inside a 120-second frame; replay JSON; and precise ground-path active fractions. Tests use local provider doubles and spend no credits.
