# Campus visual and motion audit

Audit date: 2026-10-24. Scope: character rendering, camera, map geometry, depth,
vehicle display, visual interaction semantics, and the current campus screenshot.
Population composition and schedules are audited separately in the simulation.

Visual thesis: an explorable, warm pixel campus with readable people, genuine
campus geography, and quiet scenery that makes movement and emergencies legible.
The canvas remains the primary workspace; the inspector supplies detail on demand.
Motion should communicate walking, meeting, and transport without exaggerated
gait, permanent gestures, or decorations that impersonate simulated residents.

## Findings and changes

| Priority | Finding | Evidence | Change |
| --- | --- | --- | --- |
| High | Families stand still while their activity says “family walk.” | `campus_life._arrive` chooses waiting at a park destination; the old family routine held this for hours. `ResidentLife` said “Traveling with household” for every grouped resident, including indoors. | Simulation and UI owners correct itinerary/labels. Rendering never invents movement for a stationary recorded person. |
| High | Excess families dominate the campus. | Repeating household recipes included two families per eight households, with children and shared all-day schedules. | Simulation owner replaces composition and schedules with student/staff campus life and only two nearby families. |
| High | Buildings, trees, cars and people have inconsistent depth. | `PixelWorld` placed every person above one flattened terrain/building texture and above the entire car layer. | Campus scenery is packed into shared texture atlases and placed in one sortable depth container with people/cars. Roof/canopy occlusion follows feet depth. |
| High | Every road/path segment has a visible cap and seam. | `CampusTown` painted outline/surface/outline per OSM segment; the old screenshot shows repeated rounded “sausage” joints. | Network-wide underlay passes followed by network-wide surface passes. OSM junctions now connect cleanly. |
| High | Courtyards are painted solid and pedestrian plazas are only outlines. | The old `ring` helper discarded all inner rings. Source polygons for Scott Laboratory, Hagerty Hall, Campbell Hall and Derby Hall contain holes. | Compound even-odd ground/roof paths preserve courtyard holes. Pedestrian polygons become filled plazas. |
| High | Walking gait aliases at accelerated simulation time. | One pose per 0.23 physical metres at 24× world speed can require over 100 pose changes per displayed second. | A pause-aware playback animation clock limits the visible gait to 10 poses/sec. Position and route timing still use the recorded movement. |
| Medium | Families form a rigid screen-horizontal fence. | All grouped members received a horizontal offset regardless of route direction. | Compact offsets follow the current route normal, with a small trailing position for children. Physics and recorded paths are unchanged. |
| Medium | Conversations look like permanent raised arms and floating duplicate bubbles. | Pose 7 was always selected for anyone with `partner_ids`; both `ResidentLayer` and `TownAtmosphere` drew bubbles. | Partners face each other; brief gestures alternate with rest. One intermittent bubble is placed at the actual rendered participants and disappears when indoors/in a car. |
| Medium | Parked inventory stacks at garage transfer nodes. | Up to 70 vehicles were displayed at four/five facility coordinates, which are not individual stalls. | Empty stored cars are hidden. Active trips, boarding/alighting and selected moving occupants remain visible. Simulation owner also corrects car ownership/parking. |
| Medium | Roofs dominate the scene with repeated bright stripes. | Every roof had a bright line every 16 pixels and the same rooftop appliance. | Quieter roof planes, masonry/eaves, restrained rooftop equipment, residential roof/chimney detail and an Orton clock-tower silhouette. Building footprints stay authoritative; architectural elevations are illustrative. |
| Medium | Facade windows are hidden behind the roof. | The old painter assumes one polygon winding and paints windows on the opposite-facing wall for actual OSM polygons. | Determine visible wall edges from the outer-ring winding, then paint masonry, sill bands and visible window rows. |
| Medium | Vegetation is scattered arbitrarily and ignores expanded map bounds. | Hardcoded 40-unit extents and seeded trees were unrelated to actual campus planting. | Expanded snapshots use real pinned OSM tree locations. Older recordings retain bounded seeded fallback. No invented forest is drawn outside the surveyed area. |
| Medium | Camera assumes the original 40×40 core. | Hardcoded `[19,20.5]` focus and fitting to `city.size` included padding. | Use serialized `camera_focus` and fit `map_bounds`; legacy recordings retain their original fallback focus. |
| Medium | Clicking a person's head misses them. | Picking previously measured only a radius around the feet despite the 44-pixel silhouette. | Hit-test the visible body and head, preserving repeat-click cycling in crowds. Verified by selecting Jules Reed directly on the head. |
| Medium | Off-map commuter homes can become phantom buildings. | Generic home markers, lamps, camera follow and occupancy picking operated on all places. | Exclude `is_portal` from scenery, occupancy, lamps, home icons and building picking/follow. Departed commuters still render normally. |
| Low | Garage names impersonate prominent landmarks. | A broad “Ohio Union” regex labels “Ohio Union North Garage” at the same hierarchy as the Union. | Only the exact Ohio Union building receives the landmark label. |

## Verification and limits

TypeScript and the production bundle compile. An independent QA browser renders
the expanded campus, resolves its continuous paths, displays 300 residents, and
reports zero browser errors. Screenshots live under `output/playwright/` with the
`campus-visual-` prefix. The final 1440×900 campus and residential screenshots are
`campus-visual-final-campus.png` and `campus-visual-final-neighborhood.png`; the
390×844 check is `campus-visual-final-mobile.png`. A 119-frame active-playback
sample on this Mac measured 8.3 ms median and 9.2 ms p95 requestAnimationFrame
intervals (not a cross-device benchmark). This audit does not invoke paid inference or restart the
credential-bearing local server.

Character scale is deliberately enlarged for readability; it is not a metric
human height. Small group offsets are a display convention, not new physical
locations. Depth is sorted by object ground footprint, not per-pixel 3D geometry.
Building elevations, roof materials and furniture remain illustrative artwork.
The measured plan and preserved courtyard holes are map geometry; they do not
claim a complete digital twin of building interiors or shelter safety.

## Address camera verification addendum

The follow-up found that focusing the southeast-edge Summit Street family house
left much of the viewport outside the surveyed map, and did not identify the
target building. Campus cameras now clamp to `map_bounds` using the usable
viewport, zoom and UI insets. Overview centers a smaller map with letterboxing.
Address focus draws a restrained gold footprint outline and entrance pin; panning,
ordinary focus, following and overview clear it. Resizing keeps the address in view.

The desktop inspector's actual measured right inset is supplied by the app.
Sam Lewis's house-focus check placed the map's right/bottom edges at x=1104/y=690,
before the inspector at x=1120 and above the dock. Dragging farther southeast
kept these bounds unchanged and cleared the address pin. Whole-map bounds were
`[167, 94, 937, 678]`, with the complete surveyed extent visible and no address pin.

At 390×844, selecting the address closes the inspector and hides the warning
brief during address exploration. The highlighted house remains visible above
the dock, the map extends through the usable viewport, and there is no horizontal
overflow. Opening the Warning toolbar and closing its panel restores the warning
brief. The focused flow reported zero browser errors/warnings.

Final proof images:

- `output/playwright/campus-home-focus-clamped-final.png`
- `output/playwright/campus-camera-overview-final.png`
- `output/playwright/campus-home-focus-mobile-final.png`
- `output/playwright/campus-mobile-warning-restored.png`
