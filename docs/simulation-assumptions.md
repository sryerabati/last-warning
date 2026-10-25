# Simulation assumptions and metric definitions

This is an experimental agent-based model of a fictional city, not a disaster forecast, psychological assessment, or public-safety decision system.

## City and movement

- Both layouts occupy 40 × 40 cells. New UI work uses an organic town with a winding three-cell-wide river, irregular road and footpath branches, two bridges, and explicit building footprints and entrances. All rendered paths and water cells come from canonical simulation geometry. Legacy grid scenarios retain streets at x/y 3, 9, 15, 21, 27, 33, 37 and a river at x 18–20.
- Living-town residents start an emergency at the exact selected daily frame, including their occupancy and destination. Legacy residents start at road-side doorstep nodes. Rendered parcels are inaccessible to route traversal; agents never cross buildings or unbridged river cells.
- Two fixed, protected, uncapacitated refuges are at (3,3) and (37,37) for flood and wildfire. The fire scenario assumes maintained refuge firebreaks. Tornado scenarios instead provide eight designated sturdy storm shelters: the original two, plus (9,9), (9,27), (15,15), (27,9), (27,27), and (33,21). Shelter nodes are always protected; this is a modeling assumption rather than a building-engineering result. Origins cannot be designated shelters.
- Each agent has fixed, seed-derived trust, reaction delay, walking speed (0.45–1.30 cells/tick), and an everyday priority, plus a six-neighbor Watts–Strogatz social graph with 0.12 rewiring probability. Priorities concern work, family, errands, household routines or checking on neighbors; residents with a walking speed below 0.7 explicitly account for that slower pace. Goals are saved with initial conditions. Intrinsic reaction delay is used by rules mode, not by the Bedrock action policy.
- Movement accumulates credit, capped at two cells per tick. At most three entries per nonshelter road cell per tick are allowed. Entry order rotates deterministically using keyed randomness. This approximates congestion; it is not collision-free pedestrian physics.
- NetworkX recomputes accessible shortest routes whenever closures change. A resident attempting evacuation with no route becomes stranded; a resident occupying an actively dangerous cell becomes exposed. Exposure is terminal in this model and does not mean death or injury. Indoor occupancy has an actual named place, but its logical position remains the entrance. Homes provide no additional hazard protection; rooms, interior evacuation and building damage are not simulated.

## Daily life

Daily life is a local deterministic schedule, with 288 frames of five town minutes. Households contain up to four residents sharing a home. At the default population of 300, 75 households share 64 home buildings. Residents have seeded fictional names and worker, student or neighbor roles, with distinct departure offsets and actual work/school, market, park and civic destinations. Household members are included in their social contacts.

Daily travel uses actual connected road edges, with two to four edges per compressed five-minute frame according to walking speed. It is not calibrated to real pedestrian travel time. Activity spots spread outdoor visits across reachable nearby path nodes. A conversation records co-located residents and participant IDs; it does not generate dialogue or send a warning. A multi-frame meeting may produce several observation records. Night occupancy and daily clock are saved in frames, and all residents return home before the midnight loop.

The daily preview makes no Bedrock or TRIBE calls. Starting a warning freezes the selected town tick, household profiles and positions; emergency time then advances by the configured seconds per tick. During an emergency, routine travel uses the engine's usual movement credit, congestion and current closures. Bedrock chooses whether to continue the routine or interrupt it. Ambient schedules themselves are not LLM plans.

## Flood cellular automaton

The origin becomes wet at tick zero. Each wet cell schedules four neighboring cells. River transit takes 1.1 ticks; other transit takes `4.5 + 2 * local_resistance + 5 * positive_elevation_difference`, divided by the spread multiplier. Local resistance and terrain roughness are fixed by the scenario seed. Cells above height 2.4 are excluded. The priority queue implements these asynchronous cellular transitions; it does not grow a radius or use a decorative mask.

Depth increases from 0.12 to 1.8 abstract meters at 0.025 per elapsed tick. A road closes at depth 0.30. Wetness/closures are monotonic. There is no mass conservation, drainage, storm hydrology, flood recession, or calibrated scale. The default reaches approximately 84% cell coverage by tick 120; this is deliberately severe for the demo.

## Wildfire cellular automaton

Ignition defaults to (6,12). Each burning cell schedules four neighboring ignitions. Transit is `4 × (1 − 0.65 × wind_alignment) × fuel_resistance × road_resistance / ((1 + 0.8 × uphill_difference) × spread)`. Wind points toward (0.8,0.6); seed-derived fuel resistance ranges from 0.8 to 1.45; road verges add a 1.25 transit factor. Roads stand for combustible urban-interface verges rather than burning asphalt. The river, including bridge cells, is a complete fuel break. Either bank can be selected for ignition; river origins are rejected. Ember spotting, atmospheric coupling, fuel moisture evolution, fire suppression, smoke exposure, and structure-by-structure combustion are omitted.

Cells remain actively dangerous for ten ticks after ignition. Previously burned cells remain in the recorded footprint, and burned road nodes stay closed for debris/hot-surface inspection. Consequently the active flame front differs from the cumulative affected area. Wind and slope effects follow the qualitative mechanisms described by the [National Weather Service fire weather training](https://www.weather.gov/media/zhu/ZHU_Training_Page/winds/FireWx_General_Winds/FireWx_General_Winds.pdf); all coefficients and times are illustrative, uncalibrated choices.

## Tornado track and debris

The default tornado starts at (3,35) on tick 12 and travels in direction (0.8,−0.6) at `0.45 × spread` cells/tick. The active wind footprint has radius 2.2 cells; the surrounding damage footprint has radius 3.0. Swept segments are evaluated between ticks so fast tracks do not skip roads. Roads in the core close; outer-swath roads close according to a fixed seed-derived debris draw below 0.55. The track exits the city; active danger moves away, while affected cells and debris closures remain. The simulation does not model pressure, wind speed, structural failure, tornado formation, track uncertainty, or a Fujita rating.

Residents seek the nearest accessible designated local storm shelter, rather than walking toward a distant flood refuge. This follows the [National Weather Service principle of seeking nearby sturdy shelter immediately](https://www.weather.gov/safety/tornado-during). Shelter protection and unlimited capacity are explicit simplifications. This pedestrian simulation is not guidance to evacuate a home during a tornado warning.

## Shared warning delivery

- Mobile recipients are selected using delivery reach and receive the alert after 1–4 ticks. Siren reach is the same configured reach multiplied by 0.65, with a two-tick delay.
- A model-selected or rule-selected social share sends actual messages over the social graph, with 2–5 ticks of transit per edge. Sharing requires an enabled social channel and a received warning; each resident shares at most once. No warning text is delivered through disabled channels.
- All modeled dynamics are per tick. Changing tick seconds changes reported time/exposure duration; it does not recalibrate movement or hazard transit to a physical clock.
- Scenario type, intensity and origin affect hazard mechanics and routes. Warning wording does not select or change a hazard. Both warnings in a counterfactual share the same scenario, population and physical hazard sequence. Missing disaster/decision types in legacy configuration resolve to flood/rules. Comparisons require the same simulation version and initial-condition hash; current configuration includes the decision mode and saved resident goals.

## Bedrock resident decisions

The UI defaults to actual Bedrock resident decisions. At ticks 4, 16, 32 and 56, each eligible resident receives an individually constructed context and one model-selected action: `WAIT`, `PREPARE`, `SHARE` or `EVACUATE`, plus `CONTINUE_ROUTINE` in living-town mode. Plain Bedrock Converse requests batch ten residents, with one in-flight request per service process, a 3,000-token output bound and a 60-second read timeout. Protocol `nova_resident_json_v4` is retained for legacy worlds; `nova_resident_json_life_v1` adds routine continuation. Both independently validate every resident ID, eligible action and short reason. A response must contain exactly the complete requested resident set. One bounded retry can correct an invalid response or retry a transient failure; an exhausted retry aborts explicitly. Every paid attempt is reserved in the ledger. No rule-based response or replacement model decision is substituted.

Residents have ordinary daily priorities rather than a universal goal to evacuate. Context includes actual trust, walking pace, position, state, received message, local observations, accessible shelter route, social contacts and three recent model decisions. Living-town context also includes actual household membership, home, workplace, activity and occupancy. A resident without a warning has no perceived message text. Hazard type remains unknown until a warning or local observation; observations cover active cells within three cells in each coordinate and are remembered after the hazard moves away. Provider inputs omit global hazard origins, intensity and seed. Social-contact states are a simplifying shared-information assumption. There are no physical rescue or family-reunification actions.

Wait and preparation keep the resident in place until a later model choice. Sharing sends the modeled messages and holds position. Continue routine follows the resident's actual itinerary on accessible paths. Evacuation starts or continues actual graph movement; it is available only when an accessible route exists. New closures can strand an already moving resident, and active danger causes exposure independently of what the model recommends. Residents already sheltered or exposed, or currently in an actively dangerous cell, are not sent for a new decision.

The rule mode's notice, action and social-share probabilities and preparation delay do not gate Bedrock choices. Delivery reach, channels and message transit still determine what information arrives. A received warning is marked noticed when it is included in a model decision round; this records prompt consumption, not a measured human attention response. Actual wording can influence model choices, but no validated psychological accuracy is claimed. New generations can vary even with temperature zero; replay uses the saved decisions and physical frames without another provider call.

## Rule-based resident decisions

This explicit alternative is deterministic and remains the API schema default for old configurations. The following assumptions apply to `decision_mode: "rules"`:

- Delivery and attention are separate. One tick after delivery, one fixed attention draw is compared with notice probability. Repeated ticks do not produce repeated attention trials.
- A noticed warning moves an agent to deciding. After their intrinsic reaction delay, a fixed action draw is compared with action probability × trust. Passing agents prepare for the editable preparation delay, then start evacuating.
- A noticed warning may be shared once, after at least two ticks, based on social-share probability. Each social edge adds another 2–5 ticks of delivery delay. Social sharing needs at least one direct-alert seed.
- Agents independently observe an active hazard in their cell or four immediate neighbors and begin preparation with a one-tick delay, even without a warning. This may eventually trigger agents who initially declined an alert. Burned cells and old tornado debris alone do not trigger this active-hazard observation.
- Different texts with identical rule assumptions yield identical simulation frames. Each disaster's generic/actionable presets intentionally use different probabilities and preparation delays; those values are not inferred from language or measured human responses.

## Metrics

| Metric | Definition |
|---|---|
| Population | Exact number of independent resident agents |
| Warning delivered | Unique residents receiving an alert via any enabled channel |
| Warning noticed | Rules: unique delivered alerts passing the attention draw. Bedrock: received alerts included in a resident decision round |
| Warning shared | Actual social-share events, not recipients |
| Evacuation starts | Residents with an actual start event, including those later exposed/stranded |
| Evacuated / sheltered | Residents currently at one of the safe zones |
| Hazard exposed | Unique residents with positive accumulated exposure |
| Stranded | Residents attempting evacuation and currently marked STRANDED because no accessible shelter route exists, excluding terminal exposure |
| Average alert receipt time | Mean first receipt tick × seconds per tick, measured from disaster start |
| Average decision delay | Mean notice-to-evacuation-start time among residents with both events; a locally triggered start can precede a later notice event |
| Average evacuation completion time | Mean safety-arrival minus evacuation-start time, among completed journeys only |
| Hazard coverage | Cumulative affected cells / 1600 (wet flood cells, ignited fire cells, or tornado damage swath) |
| Road closures | Number of currently inaccessible road nodes |
| Route replans | Observed invalidations of an agent's previously planned route where a replacement path exists |

Missing averages are `null`, displayed as “—”. State counts partition the population; cumulative deliveries, starts, and exposures are overlapping event measures and should not be added together. Travel-time averages can rise when a warning helps more slow residents reach safety; they do not necessarily improve with every intervention.

## Optional neural coupling

Off by default and restricted to rules mode. With an associated `REAL_TRIBE` analysis, the normalized feature is `tanh(mean(abs(predictions)))`. Notice probability becomes `clamp(base + strength * feature, 0, 1)`. No empirical neuroscience-to-behavior relationship is established. Positive/negative strengths can be compared as sensitivity experiments using ordinary rule counterfactuals. Bedrock runs reject nonzero notice-probability coupling, since their choices bypass that probability gate. Real Mini results can still be attached and displayed independently at zero coupling. Any attached analysis must match the exact current warning and registered stimulus hashes, even when coupling is zero.
