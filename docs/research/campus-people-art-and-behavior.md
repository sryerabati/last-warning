# Campus residents: readable art and credible daily life

Research memo, 24 October 2026. This is a proposed implementation specification, not a claim that the current simulator has been calibrated to Ohio State behavior. No application code, cloud services, or installed dependencies were changed for this research.

## Recommendation

Keep the existing Pixi renderer and authoritative simulation/replay architecture. Replace the tiny, mostly recolored people with original **32×40–48 logical-pixel characters**, using the oblique view and clear silhouettes of concept C and the everyday clothing diversity of concept B. Establish the camera and on-screen size before producing an entire animation atlas. Add continuous pedestrian positions, persistent households and travel groups, and real vehicle occupancy before decorative car animations.

The three generated boards are visual concepts, **not usable fixed-grid animation sheets**. They need redrawing/normalization into consistent frames, foot anchors, directions, proportions, and animation timings. The concept alternatives are:

| Direction | Strength | Main tradeoff |
| --- | --- | --- |
| [A: bold campus](campus-concepts/a-bold-campus-v2.png), compact 24×32 | Strong readability, inexpensive animation, game-like charm | Exaggerated heads can feel less natural |
| [B: everyday campus](campus-concepts/b-everyday-campus.png), 32×48 | Recognizable clothing, age and body variation | Primarily front-facing concepts; perspective needs rebuilding |
| [C: living diorama](campus-concepts/c-living-diorama.png), 32×40 | Best camera compatibility and directional silhouettes | Needs B's clothing variety and consistent production frames |

Recommended production experiment: make **six complete C-style characters** before expanding the roster: two differently dressed students, faculty, a facilities worker, an older neighbor, and a wheelchair user. Test them against actual campus grass, brick, paving, snow and night palettes. Then produce 12–18 base appearances with independent hair, skin, clothing and accessories. Use synthetic identities; appearance must not determine intelligence, trust, emergency compliance or social class.

## What the current code actually does

Inspected `frontend/src/pixel-world/{Art,ResidentLayer,PixelWorld}.ts`, `frontend/art/last-warning/generate_atlas.py`, the public atlas manifest, and `backend/app/simulation/life.py`.

- `CELL` is 64 world pixels. Resident frames are **12×20 pixels**, enlarged 1.35× on the organic map. Their painted bodies occupy less than the full frame.
- The atlas has 12 variants, four directions and four poses. Most differences are shirt/skin colors and a hat; body shape, outfit silhouettes and movement are almost identical.
- Residents share exact cell-center coordinates. Several people at the same location therefore cover each other. Sorting by foot position does not resolve physical overlap.
- The renderer follows recorded paths and uses actual movement direction. Indoor residents are hidden only after arrival. These are useful existing behaviors to preserve.
- Normal desktop focus uses camera scale `.75`; it does not reliably enlarge a selected resident compared with the initial view. Overview scales every person down with the map; there is no semantic level of detail.
- Daily life currently has 288 five-minute frames, fixed four-person households, roles assigned in a repeating worker/worker/student/neighbor pattern, common schedules with small time offsets, and shopping/park interactions based on co-location. Vehicles and meaningful boarding/occupancy are absent from this life model.

These findings are source-code observations. The pixel calculations below are derived from the current camera formulas, **not measured browser screenshots**. Actual canvas viewport dimensions can differ from browser dimensions because of the application layout.

## Screen-pixel budget

`displayed frame height = native frame height × resident art scale × camera scale`.

| Canvas example / mode | Current camera scale | Current 20px frame × 1.35 | Proposed 40–48px frame × 1 |
| --- | ---: | ---: | ---: |
| 1440×900, initial single view | .75 | 20.3 CSS px | 30–36 CSS px |
| 390px-wide mobile, initial view | .625 | 16.9 CSS px | 25–30 CSS px |
| 1440×900, fit current 40×40 world | .2695 | 7.3 CSS px | 10.8–12.9 CSS px |
| 390×844, fit current world | .1523 | 4.1 CSS px | 6.1–7.3 CSS px |

Opaque body height is smaller than frame height. Device pixel ratio must not be mistaken for visible CSS size. Simply drawing more detail into a sprite will not fix the overview.

Proposed acceptance targets, chosen for this product rather than taken from behavioral research:

1. **Street view:** 28–36 CSS px frame height; recognizable outfit silhouette, facing direction and walking/idle state without selecting the person. On a narrow screen, begin closer to the town rather than shrinking everyone to fit it.
2. **Resident focus:** 48–64 CSS px frame height. Focus must visibly zoom toward the selected person; avoid a jump that loses their surroundings.
3. **Campus overview:** use restrained 6–9px person/group markers, density grouping and a persistent selected-person marker. Do not promise that hundreds of full bodies remain individually readable.
4. **Interaction:** proposed 44px touch targets, independent of art dimensions; expose overlapping residents with a cycle/picker. Names appear on selection or deliberate hover, not across the entire map.
5. **Contrast:** silhouette remains identifiable on grass, brick, asphalt, snow and at night. Use a toned outline and foot shadow; do not rely on shirt color alone. Storm effects must retain a visibility budget around people.
6. **Motion stability:** fixed foot anchor across all directions and poses; no height jumps, mirrored bags changing shoulders, or feet sliding during idle. Retain nearest-neighbor sampling and consistent camera rounding.

Camera-independent minimum sizes should be bounded. Expanding full-size people indefinitely while zooming out would visually occupy whole buildings. Switch representation at a defined threshold instead. Physics footprints, hazard exposure and routing must never grow just because the visual sprite grows.

## Character and animation specification

Use a small number of coherent silhouette families: hoodie/backpack, coat/tote, sweater/slacks, workwear, light summer clothing, winter coat/scarf, older adult with optional cane, wheelchair user, and visiting parent/child. Hair, head coverings, body proportions, skin and outfit combinations are independent choices. Students are primarily adults; a family with children is a distinct synthetic visiting/local household, not every student household.

Base production set:

- Four genuine view directions; six walking frames per direction is a proposed initial quality target. Reuse timings where appropriate, not mirrored asymmetric accessories.
- Two subtle idle frames, a brief look-around, phone-check, wave and conversation gesture; seated and queueing poses where places support them.
- A short boarding/alighting sequence at a vehicle door. Do not make a standing pedestrian vanish halfway across the road.
- Distinct wheelchair rolling/idle animation rather than substituting walking legs. Route accessibility follows known graph features, with unknown accessibility shown honestly.
- Weather clothing and posture variants can reuse silhouettes. Speed and gait must follow the recorded movement state; a frightened animation alone is not an emergency decision.

Randomize animation phase deterministically by resident ID so the crowd does not march in synchrony. Idle actions must be short, occasional and interruptible. Tie conversation bubbles, waiting and waving to actual state transitions, not an unrelated decoration timer. In reduced-motion mode, retain state changes and selection cues while removing bounce and unnecessary loops.

The official [Aseprite sprite-sheet documentation](https://www.aseprite.org/docs/sprite-sheet/) describes exporting animation frames into sheets, and its [CLI documentation](https://www.aseprite.org/docs/cli/) supports PNG plus JSON exports. These are useful interchange patterns; no paid authoring-tool purchase is required for this project. The existing atlas generator remains an available build path. Parent research covers Pixelorama and the final authoring tool choice.

## Natural behavior: what evidence supports and what remains an assumption

[Moussaïd et al. (2010)](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0010047) observed social groups and found that conversational relationships affect walking formations: groups often use side-by-side arrangements with space, changing shape in denser conditions. This supports explicit social groups and width-sensitive formations. It does **not** establish the fraction of Ohio State pedestrians traveling in groups, local walking speeds, or campus mode shares. Do not import the paper's commercial-street percentages as campus facts.

[Drury et al. (2016)](https://onlinelibrary.wiley.com/doi/full/10.1002/ejsp.2146) surveyed 1,240 adults affected by the Chile earthquake. Observed support and shared identity were associated with support provision. This supports including helping, coordination and expectations of others' assistance among possible behaviors. It is a survey from another disaster context, not a numerical calibration for this campus and not proof that everyone always helps. Avoid a universal “panic makes everyone irrational” rule.

[Park et al. (2023)](https://arxiv.org/abs/2304.03442) demonstrated a 25-agent sandbox using observation, retrieved memories, planning and reflection. It provides useful architecture for continuity and believability. The study does not validate LLM outputs as forecasts of real emergency behavior. Our use should be a smaller, budgeted adaptation, with executable plans checked by the simulation.

Campus population weights, student commuting, class schedules, household sizes, walking speeds, vehicle ownership and reaction delays need their own relevant data or explicit scenario assumptions. The current four-person household rule is especially inappropriate for a campus containing roommates, solo commuters, service workers and visiting families. The geography and hazards research memos provide complementary sources; do not infer demographic composition from a map.

## Proposed resident architecture

Separate five layers rather than asking the model to animate every person:

| Layer | State / responsibility | Execution |
| --- | --- | --- |
| Identity | Synthetic name, age band, role, home, regular destinations, accessibility needs, relationships | Persistent seeded data |
| Agenda | Time windows, commitments, meals, errands, appointments and travel feasibility | Local planner; optional cached high-level LLM plan |
| Intent and memory | Observed warning, relevant recent events, chosen next action and reason | Existing Bedrock decision path, bounded event-driven calls |
| Movement and activities | Routes, queues, group slots, doors, boarding, speed, interaction timing | Deterministic local simulation |
| Presentation | Sprite, gait, camera LOD, selection and informative cues | Pixi, replaying recorded states |

Give students different class blocks, off-campus homes or dorm rooms, meals and jobs; faculty different teaching/office/research commitments; staff shifts and service destinations; neighbors errands and visits. These are proposed role templates, not claims about exact OSU schedules. Use overlapping time windows, lateness tolerance and transport constraints rather than having everyone leave at 7:10. Persistent obligations create understandable individual stories.

Memory entries should be structured, bounded and grounded: `event_id`, time, observation, place, source, affected people, and unresolved intention. An agent knows what it observed or was told, not the entire hidden map or another person's thoughts. Save model/version, prompt context, selected action, reason, actual token usage and any validation rejection for reproducibility.

Trigger Bedrock at meaningful decisions—warning received, route closed, intended shelter unavailable, companion separated—not every rendered frame. Supply a small executable action catalogue and current constraints. Validate destination existence, permissions, hazard constraints and feasible modes before committing a plan. Route planning, collision avoidance and animation remain local. A missing budget or model response must be visibly labeled; never relabel a local fallback as an LLM decision. This protects the existing total-project spending cap while preserving actual LLM agency where it matters.

## Families, roommates and social interactions

Use separate `household_id`, relationship edges and `travel_group_id`. Roommates share a home without moving together all day. A parent and child may share a trip; friends can meet for lunch without belonging to one household.

Create persistent meeting records with participants, location, start window, expected duration and status. A conversation starts when participants arrive, persists briefly, updates their recent memories, and ends for a reason. It should not be recreated every simulation frame from sorted co-located IDs.

Travel groups need a common goal, leader/coordination policy, formation slots and a reunion point. Use side-by-side pairs where path width allows, compress through narrow connectors, slow or wait when a companion falls behind, and rejoin at a safe destination. Membership should not compel a person to enter an unsafe area. Dependent members require an assigned companion; adults may explicitly split. These are design policies requiring sensitivity testing, not measured universal human rules.

The first movement upgrade should place recorded positions within walkable corridors and reserve simple passing/queue slots. Purely cosmetic random offsets would disagree with selection, contact and hazard coordinates. More elaborate reciprocal avoidance can be evaluated later; its collision guarantees depend on model assumptions and do not make it a calibrated model of human interaction.

## Cars and transit: complete lifecycle

Represent a trip as stages, following the useful separation in [SUMO's person specification](https://sumo.dlr.de/docs/Specification/Persons.html) and [intermodal-routing documentation](https://sumo.dlr.de/docs/IntermodalRouting.html): a person can walk, wait and ride across one journey. This is an architectural reference; integrating SUMO itself is not required for the first implementation.

Proposed lifecycle:

`Plan trip → Walk to parked vehicle/stop → Wait at boarding point → Board → Ride/drive → Park/stop → Alight → Walk to destination → Enter/activity`

Each vehicle has one ID, capacity, actual occupant IDs, driver where needed, location, route and parking/stop state. Each person has exactly one location mode: walking, aboard vehicle, or inside a destination. While riding, a person's world position derives from the vehicle, and their pedestrian sprite is suppressed. Selecting the vehicle reveals occupants; selecting an occupant follows the vehicle.

Required invariants and visible consequences:

- A car starts at an actual parking node. It does not materialize at any pedestrian's current location.
- Boarding requires the assigned vehicle to be stopped at the agreed connector and capacity to be available. A family reserves the needed seats before the trip begins.
- A driver cannot depart while required companions are still boarding. If someone is absent, the group waits, times out or changes its explicit plan.
- Shared passengers produce one moving vehicle, not four duplicates. Pedestrians do not remain visibly walking beneath it.
- Vehicle routes use driveable edges; pedestrians use sidewalks/crossings/connectors. Cars cannot use a campus footpath because the pedestrian shortest path is shorter.
- Parking and stops have finite capacity. Arrival includes parking/waiting/alighting time; the final walk to a building is real.
- Transit stops, routes, headways and capacity need sourced data or declared scenario settings. Do not label a decorative bus a live CABS service.
- Weather or a blocked area can invalidate a stage; replan from the actual current state. Never teleport the household to keep its appointment.

Distance and speed must eventually use geographic meters and simulation seconds. The current cell-edge movement per five-minute frame is not enough to claim real travel-time accuracy. Preserve the original replay identity with a versioned schema when adding continuous positions and vehicle events.

## Acceptance gate before scaling up

These are proposed tests and targets, not completed test results:

| Area | Must demonstrate |
| --- | --- |
| Character prototype | Six normalized characters remain legible at actual 28–36px street scale on all five backgrounds; four directions and transitions have stable anchors |
| Camera | Desktop and mobile default views meet size target; focus reaches 48–64px; overview uses honest markers; compare view does not silently halve readability |
| Interaction | Mouse/touch selection works for overlapping people, a passenger, an indoor person and a group; keyboard focus remains usable |
| Movement | No path crosses a non-walkable building/water/road restriction; idle feet remain stationary; narrow connectors form queues without persistent overlap |
| Groups | Two-person walk, three-person lunch meeting, family car trip, delayed companion and deliberate split all have visible, traceable state changes |
| Vehicle occupancy | Capacity never exceeded; occupants cannot exist in two vehicles or also as pedestrians; exact count conserved across boarding and alighting |
| Emergency decisions | Only received/observed information reaches each agent; valid model decision changes action; rejected/infeasible choices and budget fallback are honestly recorded |
| Replay | Same seed and saved decision log reproduce positions, groups, occupancy and conversations; backward seek restores all entities correctly |
| Performance | Measure the user's Mac at 300 residents first, then 600 as a stress case; target p95 frame time under 16.7ms at target viewport, or document a deliberate lower target; no unbounded memory growth after repeated replay |
| Accessibility | Reduced motion remains informative; selection is not color-only; winter effects do not hide people; readable ordinary numerals in UI |

The official [Pixi performance guide](https://pixijs.com/8.x/guides/concepts/performance-tips) favors sprite sheets and attention to batching, draw order and expensive redraws. Use atlas sprites, pooled markers, restrained filters and measured culling. Profile actual CPU/GPU time before introducing a new engine. An official [Pixi performance skill](https://github.com/pixijs/pixijs/blob/dev/skills/pixijs-performance/SKILL.md) is available under its stated MIT license; review against installed Pixi 8.22 and pin a reviewed revision rather than installing an unverified community skill. Parent research separately identified the official `pixijs/pixijs-skills` collection.

## Implementation order

1. Normalize the six-character art experiment and build an actual-scale contact sheet over screenshots; fix camera/focus/LOD first.
2. Introduce a versioned resident/household/group/vehicle schema and authoritative continuous positions.
3. Make one complete family car trip and one peer-group walking/lunch trip work, including replay and selection, before populating the campus.
4. Add varied campus agendas and bounded memory-based Bedrock intent; preserve spending and traceability controls.
5. Expand the atlas and campus population, then integrate hazard-specific reactions from the separate evidence memo.
6. Run the acceptance gate and clearly separate researched facts, scenario assumptions and simulated outcomes in the advanced information panel.

The desired experience is a readable campus full of people with understandable commitments. “Looks alive,” “uses an LLM,” and “predicts real behavior accurately” are different claims; only the first two can be established by the initial implementation and demo tests.
