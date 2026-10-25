# Campus audit and corrections

This audit used three independent reviewers for resident behavior, real geography/housing, and visual motion. The lead also checked emergency integration, historical replay, and the resident inspector. All people and their home assignments are fictional; the campus plan is sourced geography.

## What was wrong

The reported problem was real. The former 300-person scene contained **34 families, 119 family members and 51 children**, but only 114 students and no graduate students. Its repeating schedules sent nearly everyone to one of three parks. At 13:00, **258 residents were stationary at parks and nobody was walking**. “Family walk” was the name of a stationary activity, not a walking route.

The complete findings and implementation details are in these three audits:

- [Behavior audit](research/campus-behavior-audit.md): household proportions, employment, names, contacts, timings, waypoint transitions, accessibility, car journey choice, conversations, appearance and route-cache memory.
- [Geography audit](research/campus-geography-audit.md): clipped homes, shared entrance proxies, capacities, building-use classification, geographic scale, actual housing blocks, off-map commuters, shelter permissions, exterior-only paths and mapped vegetation.
- [Visual audit](research/campus-visual-audit.md): disconnected-looking paths, courtyard holes, depth, gait, group formations, conversation gestures, vehicle stacking, roof/facade detail, map bounds, camera and picking.

## Corrected behavior

The default population is **202 undergraduates, 47 graduate students, 16 professors, 16 staff, 15 neighbors, two caregivers and two preschool children**. Only two three-person households are families. Each occupies its own complete house footprint in the University District. Students use residence halls/apartments, and some university workers commute from outside the map.

The working parent follows a work/teaching schedule independently. A caregiver accompanies a preschool child for a short afternoon outing. Roommates have individual names and schedules. Social ties are reciprocal. Classes, lunch, study, errands and home time are staggered; outdoor breaks are brief, and leisure routes traverse different waypoints instead of freezing under a walking label. Home/routine allocation is checked against the appropriate step-free graph, without claiming that the real entrances are certified accessible.

Meals and coffee use explicit mapped service evidence and show the actual venue name. A mixed-use building can contain a restaurant without becoming a second duplicate building/capacity. Generic retail buildings are no longer assumed to sell meals.

Car journeys compare the entire trip with walking, including access to the car, directed roads, parking transfers and the final walk. A car is used only when it saves meaningful time. Empty garage inventory is hidden rather than rendered as overlapping cars at a shared facility coordinate. Residents and vehicle occupants are conserved through boarding, travel and exit.

## Expanded world and visual corrections

The scene now spans approximately **1.54 × 1.17 km**, retaining the Oval while adding South Campus and residential streets east of High toward Indianola and Summit. World size increases from 40 to 68 units; physical scale stays approximately 24.25 metres/unit. People do not become smaller because the map expanded.

The renderer uses the new source's 3,438 mapped tree positions, continuous path/road surfaces, filled pedestrian plazas, preserved courtyard openings, quiet roofs, visible masonry/window details and distinct small residential roofs. Buildings, trees, people and cars share a depth-sorted scene. Walking animation has a bounded visible cadence; partners turn toward each other and gesture intermittently. Households no longer slide around in a rigid horizontal line. The readable pixel numerals are preserved.

The population inspector groups residents by role and local family, and a resident's Home or Study/Work address can center the map on that actual destination, with a clear location marker and camera bounds that keep nearby streets visible. Boundary commuter homes are explicitly off-map and have no fictional house or occupancy marker.

## Additional integration fixes

- Weather masks, coverage denominators, origin validation and controls now use the expanded map dimensions instead of a hardcoded 40-unit square.
- A resident cannot select a stranger's house or dorm as a public refuge. Their own residence can still be protective. Garages and boundary portals are not treated as indoor storm shelters.
- A commuter at an off-map home is neither exposed to the scene's weather nor counted as sheltered inside a campus building. Normal exposure resumes when they enter the scene.
- Historical recordings use their stored geography and motion, including valid outward escape from a public-safety closure. New runs identify the new world/day/engine versions. Rerunning an old world selects an event origin in the current map rather than silently reinterpreting its old coordinates.
- The inspector only says “Traveling with household” during actual travel. Preschool children and parents are identified accurately, without redundant home/work rows for someone whose activity is at home.

## Evidence and limits

Final verification on October 24, 2026:

- **255 backend tests passed**. Ruff and the production TypeScript/Vite build passed. The suite retains one dependency deprecation warning; Vite notes the existing Pixi chunk size.
- The default 300-person day has **105 occupied homes, two families and 31 owned cars**. A two-minute full-day sample peaks at **13 residents waiting in parks and 69 walking**, with no unreachable residents or stationary activities mislabeled as walks. The car audit finds 26 daily car trips, all faster than the corresponding complete walking journey. All 351 meal/snack/coffee stops have appropriate mapped service evidence.
- Desktop and mobile inspection covers campus motion, address focus, whole-map framing, household navigation and the readable pixel UI. Location focus highlights the building and entrance; the mobile inspector and warning card no longer cover the selected house.
- The current-world paired integration is **verified true** in [`campus-district-v21-bedrock-mini-e2e.json`](../output/campus-district-v21-bedrock-mini-e2e.json): two severe-thunderstorm warnings, 40 residents, 121 frames per warning, and **240 actual Bedrock decisions per warning**. It verifies shared initial conditions, recorded motion, passenger conservation, replay and comparison persistence. Genuine local Mini prediction artifacts were reused for their exact matching warning text, with hashes/provenance checked; this validation did not rerun Mini inference.
- The saved comparison is `ae38c792-0def-4b2b-8343-fd518e5cd4b7`. The final pair cost approximately **$0.0113**, bringing the application's tracked project total to **$0.4151**, below the $30 project cap. This is application accounting, not a verified AWS billing statement.

Run `python scripts/audit_campus_population.py` for a fresh, local whole-day population audit. Its JSON report at `output/campus-population-audit.json` records hourly activity counts, family homes, maximum park crowd, movement and unreachable routes. It makes no model requests. Regression tests additionally cover populations 30/300/1,000, passenger conservation, terrain/door geometry, historical replay, expanded hazard bounds and off-map exposure.

This is an educational game simulation. Household proportions, schedules, building capacities, interiors, driving speeds and emergency behavior have not been calibrated against observed campus behavior. The traffic model does not include signal timing, lane changes, a full collision solver or pedestrian right of way. Footpath routing and step avoidance are not an accessibility certification. Artistic building elevations are illustrative; the source supplies the measured plan. These remaining model boundaries are documented rather than presented as established real-world accuracy.
