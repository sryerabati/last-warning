# Campus behavior fidelity audit

Audited 2026-10-25. This records the baseline inspected during the cinematic/audio repair, before concurrent fixes. It distinguishes verified implementation defects, deliberate simplifications, and research-backed next steps. It does not claim that synthetic residents predict Ohio State students or that scenario buildings are officially designated shelters.

## Implemented follow-up · campus engine 3.0

The elapsed-time, crossing, calendar and transit recommendations below are now implemented. The original table is retained as the audit trail, not a list of current defects.

- Delivery, attention, preparation and decision opportunities use elapsed seconds independently of recording intervals. Five base Bedrock opportunities remain bounded; authority updates can add opportunities. Identical runs sampled at 5, 10 and 25 seconds preserve decisions, events, exposure and final positions.
- Cars and buses accelerate, observe same-lane headway, reserve conflicting crossing movements and yield. Walking groups wait at conflicts and resume along their recorded paths. This is deterministic traffic coordination; it does not reproduce live traffic signals or collisions.
- Teaching weekdays, weekends, class breaks with offices open and university closures generate different agendas. The chosen day repeats for reproducibility.
- A bounded CC-corridor shuttle uses six mapped stops, service windows, finite seats, stop queues, continuous boarding/alighting, rides and walking continuation. It is not the full official route. See [calendar and transit sources](campus-calendar-transit.md).
- Swept tornado contact catches residents crossed between saved frames. Saved contact episodes interrupt movement and drive the visible fall/bracing, debris and recovery poses. The funnel follows the same ground trajectory. These are illustrative physical responses; no injury or fatality model is claimed.

Component-specific lightning versus wind/hail protection, empirical campus calibration, actual opening hours and live bus/signal feeds remain outside this implementation.

Verification on this build: **317 backend tests and 50 frontend regression checks passed**, with a successful production build and clean lint for the application/test scope. the production 300-resident teaching-day audit completed 21 bus trips, returned all residents home, and found no duplicated passengers, capacity violations or rider-position mismatches. Cold generation took 58.142 seconds under concurrent tests, including 8.975 seconds of map initialization; subsequent identical previews use a bounded cache. Browser checks exercised the closure preset, mobile travel drawer, real paired replay, actual occupied bus sprites, and tornado fall/recovery/seek/reduced-motion rendering.

The real paired tornado demo recorded 480 Bedrock choices in 48 calls, with no invalid responses. Both genuine local Mini artifacts were verified (generic: 6×20,484; actionable: 15×20,484). Successful calls cost an estimated $0.01167509. Including a source-reload-interrupted verification attempt, this audit added $0.01657509 to accounted spending; total project ledger $0.516439875, below the $30 guard. Ledger values include conservative reservations and are not an AWS billing reconciliation. Evidence lives in `output/campus-behavior-v3-e2e.json` and `output/campus-transit-full-day-audit.json`.


## Immediate findings

| Priority | Finding and code | Consequence | Bounded correction / acceptance test |
| --- | --- | --- | --- |
| P1 | `campus_engine.py: CampusSimulation.broadcast/context/available_actions` treats siren receipt as receipt of the full warning text. | A person hears a tone, knows every word of an unseen message, and can share it. Indoor people receive the same siren draw as outdoor people. | Separate an outdoor warning cue from delivered text. Tone-only cue yields no `perceived_warning`, no text-delivery event, and no `SHARE` of an unseen message; it can motivate seeking shelter. A later mobile receipt must still deliver the text. |
| P1 | `campus_engine.py: shelter` orders feasible buildings by straight-line entrance distance. | A nearby-looking building with a large route detour can beat a building reached sooner on the actual graph. | Rank feasible walking routes by length; retain capacity, private-home access, step-free and hazard-mask checks. Test a nearer entrance behind a detour versus a farther entrance with a shorter route, inaccessible shortcuts, ties, and no-route cases. Mixed car/walk travel needs a time cost, not an unqualified combined length. |
| P1 | `campus_engine.py: DECISION_TICKS/broadcast/rules`, `schemas.py: ScenarioConfig` use tick-based response timing while hazard defaults change seconds per tick. | Changing recording resolution or hazard changes message/decision timing even with the same behavioral parameters. | Schedule delivery and decision opportunities in elapsed seconds; keep output sampling separate. Compare the same scenario at two resolutions, allowing only integration tolerance. This needs an explicit model-version change rather than a silent reinterpretation of saved `response_delay`. |
| P2 | `campus_life.py: _move/_step_unit` has independently moving units, constant vehicle cruise speed, and no intersection occupancy, headway, or crossing delay. | Cars and pedestrians can pass through each other's space; road travel times are not traffic estimates. | Start with deterministic crossing conflict zones and vehicle headway/queues, then acceleration. Test competing movements, starvation prevention and repeatability. This is a deliberate model extension, not a parameter that can be fixed from a national mean. |
| P2 | `campus_life.py: make_campus_profiles/_target` repeats the same authored day with modulo-24-hour time. | Weekend, autumn-break and ordinary class-day behavior cannot differ. | Add explicit scenario calendar/day type; distinguish no-classes/offices-open from a full closure. Test a teaching day, weekend, break and office holiday. Do not implicitly bind reproducible scenarios to the computer's current date. |
| P2 | `campus_hazards.py: protected/suitable` uses one overall shelter predicate. | An enclosed vehicle's lightning protection cannot be represented separately from wind/hail exposure; generic solid-building protection also hides differing internal refuge requirements. | Split hazard-component exposure before changing protection. An enclosed metal-topped vehicle with windows up can reduce lightning exposure without being declared universally safe from severe wind, hail, flood or tornado. |

### Corrections shipped in campus engine 2.2.1

The audit led to three verified repairs: outdoor siren cues are separate from delivered warning text; feasible shelter destinations are ranked by actual route travel time (including drive/walk transfer when relevant); and Bedrock retry recovery preserves valid model choices while re-requesting only invalid or missing residents. The subsequent engine 3.0 follow-up above implements the timing, traffic, calendar and transit extensions; component-specific protection remains future work.

Validation: 275 backend tests passed, including cue/content, routing and partial-retry regressions. A bounded real Bedrock run completed 20 model decisions over two rounds with no validation errors. See [campus emergency engine](../campus-emergency-engine.md) and `data/bedrock-campus-v2-smoke-test.json` for the recorded verification. No model choice was synthesized as a fallback.

### Reproduction actually run

A local Python diagnostic instantiated ten residents, seed 42, at campus minute 700 (11:40), with only `siren` and `social` channels and 100% configured delivery reach. After broadcasting and advancing to tick 1, residents 0, 3, 6, 7, 8 and 9 were all indoors, all received the exact warning text, and all had `SHARE` available. No provider call was made. This confirms the cue/content error independently of Bedrock output.

The same diagnostic read the actual defaults and fixed decision ticks `(2, 8, 24, 56, 96)`. First scheduled model decisions occur at 10 seconds for flood, 20 seconds for public safety, 60 seconds for thunderstorm, and 240 seconds for blizzard. The 1–3-tick mobile delivery window becomes 5–15 seconds for flood but 120–360 seconds for blizzard. These are authored timing consequences, not measured differences in human response to those hazards.

## Warning knowledge and decision architecture

Franklin County describes outdoor sirens as alerting people outside, using tones **or** spoken messages. It separately describes device-based phone/text/email alerts. Therefore it would also be inaccurate to say that every local siren is incapable of speech. The simulator's generic `Sirens` option presently has neither a spoken payload nor speech intelligibility. Treat it as a tone cue; add an explicitly modeled spoken payload only if the product later needs that distinction. [Franklin County alerting and warning](https://www.franklincountyohio.gov/Agency-Directory/Emergency-Management-and-Homeland-Security/Alerting-Warning) (accessed 2026-10-25; local system scope).

NIST's 2011 campus/building warning review describes why initiating an alarm sound alone does not guarantee that occupants understand the hazard or take suitable action. That supports separating cue detection, message access, interpretation and protective action; it does not supply calibrated probabilities for this OSU population. [NIST Technical Note 1689](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=907983) (February 2011; research review, not a current local field measurement).

OSU's current alert documentation distinguishes initial general messages from later detailed information, provides automatic enrollment for registered current campus members, and offers a temporary visitor opt-in. A more faithful future delivery model can distinguish campus-affiliated enrollment, voluntary visitors, message updates and channels. Do not infer enrollment from a person's surname or appearance; do not invent per-group failure rates. [Ohio State Crime & Safety Notices](https://dps.osu.edu/alert-notices) (accessed 2026-10-25).

The existing architecture is useful: Bedrock chooses an intention, while the local engine checks actions, routes, occupancy and capacity. Keep this separation. A valid model response is not evidence that the human behavior is accurate, and successful rerouting must not be fabricated if the local graph has no route.

### Minimal siren fix without a public-schema migration

1. Add `siren_heard` and a cue timestamp to transient resident metadata. Filter the authored siren coverage draw to outdoor, in-scene people at delivery time. Filtering indoors is a conservative scope choice, not a claim that nobody can hear a siren through a window.
2. Record `warning_cue_heard` separately. Keep `received`, `receipt_tick`, `noticed` and the existing receipt metrics for the delivered text pathway.
3. Add `perceived_cues` to the model context. A tone alone must leave `perceived_warning` null; it must not reveal exact hazard location, message instructions, or the global shelter-hold countdown.
4. Permit shelter-seeking on a heard warning cue, using the same local route validation. Preserve `SHARE` eligibility only after a message is actually received. A future “tell a nearby person that I heard a siren” action would need distinct content, not reuse unseen text.
5. Give the deterministic baseline a cue-response path, and distinguish that cue from an observed nearby hazard. Preserve the provider rule that only listed actions may be selected.
6. Test later mobile receipt, duplicate cues, indoor/off-map exclusion, follower coordination, no unseen text sharing, and stable receipt/notice metrics. No database migration or new user configuration is required for this minimal change.

FEMA training identifies message source, specificity, consistency, access and functional needs as factors affecting response. Its practical warning components include hazard, location, timing, source and protective action. A useful educational UI improvement is a small warning-completeness view and an inspector showing what each resident actually received. Missing information should remain missing; do not turn a model's plausible guess into an official update. [FEMA IS-242.c communication material](https://emilms.fema.gov/is_0242c/groups/203.html) (accessed 2026-10-25; guidance, not fitted behavioral coefficients).

## Movement, shelter and daily life

`campus_life.py` already follows graph routes, moves caregiver/child units together, lets other adults make independent trips, reserves parking, records boarding/alighting and applies step-free constraints. Retain these mechanics. The existing authored walking-speed range (roughly 0.85–1.45 m/s depending on profile) is plausible as a scenario range, but has not been calibrated against campus trajectories. FHWA's intersection research documents variation in crossing speeds and start-up behavior; a signal-design speed is not a universal agent speed or an exact age-specific rule. Use a per-person mobility capability and measured local observations if calibration is later attempted. [FHWA aging-road-user intersection evidence](https://highways.dot.gov/safety/other/older-road-user/handbook-designing-roadways-aging-population/chapter-7-intersections) (accessed 2026-10-25; research synthesis with studies from other locations).

Current graph access tags and authored entrances are not verified opening hours, accessible routes or emergency shelter designations. `campus_world.py` already labels those limitations. Add explicit `open/closed/unknown` availability and a source for each verified facility only when the information exists. Unknown should not silently become “officially open.” Keep private houses restricted to their residents.

The most useful next living-world feature is calendar-aware trip generation, then real transit mechanics. The Registrar's 2026 calendar, updated March 3, distinguishes October 15–16 autumn break (no classes, offices open) from September 7 Labor Day (no classes, offices closed). Those are materially different agendas, so one general “holiday” switch is insufficient. [Ohio State academic calendar](https://registrar.osu.edu/academic-calendar/academic-calendar-5-year-view-2023-2028/) (2026 academic scope; subject to change).

CABS is free and has published routes, directions and schedules. Its 2026–27 page lists different weekday/weekend/break operation, reduced service during academic breaks, no university-holiday service and a home-football-day suspension before kickoff. A bus should be a vehicle on a verified route with stops, waiting passengers, boarding, capacity and missed-service behavior before it is presented as transport. Headways can drive authored departures; they are not precise observed arrival times. [Ohio State CABS](https://ttm.osu.edu/cabs) (2026–27 schedule, accessed 2026-10-25).

Suggested transit tests: no boarding away from a stop; no passenger aboard two vehicles; correct route direction; full-bus queue retention; stop dwell; breaks/weekends/holidays; missed service falls back to a feasible walking or waiting choice. This belongs after the current warning/routing repairs, not in a rushed decorative bus layer.

## Hazard fidelity and honest results

The current 30-minute lightning hold is evidence-aligned: NWS recommends a substantial building or enclosed metal-topped vehicle with windows up and remaining sheltered for at least 30 minutes after the last thunder. The code's authored repeated thunder resets are educational weather events. Separate that global event history from what each resident has heard; only a delivered authority update should give them an official all-clear. [NWS lightning guidance](https://www.weather.gov/safety/lightning-tips) (accessed 2026-10-25).

The present map-wide weather fields, fixed storm/blizzard durations and global speed multipliers are authored conditions. They are not forecasts, historical reconstructions, injury models or estimates of how often Columbus experiences an event. Exposed-person seconds can compare paired synthetic runs; they must not be labeled casualties or risk reduction percentages without a validated harm model.

For severe thunderstorms, track lightning, hail and wind components separately before claiming car safety or comparing different refuge types. For the abstract public-safety scenario, retain only an avoidance region, authority updates, access constraints and generic shelter/egress choices. There is no need for weapon, attack or perpetrator modeling.

## Validation order

1. Repair cue/content separation, invalid-action handling and route-cost selection with deterministic fixtures. Do not spend on the provider until these local contracts pass.
2. Add elapsed-time invariance checks, route obstruction at mid-edge, occupied-shelter rejection and late message/update delivery. Record a model-version boundary for changed timing semantics.
3. Compare identical population, geography, initial positions and random draws between warning variants. Report delivery, actual knowledge, first protective action, feasible arrival, unmet need and exposure separately.
4. Run multiple seeds and show variation before drawing conclusions from one cinematic replay. Preserve model/version, prompts, provider usage and replay provenance. A prettier animation or coherent model explanation is not validation.
5. For later empirical work, collect consented, aggregate campus pedestrian counts/travel times and observation windows; compare time-of-day/weekday occupancy and route choices. Do not use university-wide enrollment as the denominator for a tiny campus scene or infer behavioral traits from names, skin color or clothing.

Recommended product organization: the simulator stays the main view; each resident inspector shows current trip, group, transport, received information and most recent intention; a compact run panel shows outcomes; advanced settings hold authored parameters; an evidence drawer distinguishes sourced geometry/guidance, scenario assumptions and unmodeled systems. This makes the game informative without claiming precision the engine does not possess.
