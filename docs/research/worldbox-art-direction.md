# WorldBox reference study and original Last Warning art direction

Research and planning only, 2026-10-24. No application/runtime changes, installs or paid inference calls were made for this study. The existing verified simulator remains the implementation baseline. Recommendations below describe proposed work, not features already implemented.

## Direction

**Visual thesis:** a richly inhabited pixel-art river city viewed as a living miniature, with compact emergency instruments built into the game frame.

**Content plan:** the world fills the screen; a small command strip runs the warning; the bottom toolbelt controls observation and time; selected people, messages and scientific detail open only when requested. Every screen, including history and Mini details, belongs to the same game surface.

**Interaction thesis:** pan/zoom from the whole city into an individual pedestrian; animate only actual movement and recorded events; let each disaster transform the same recognizable place. A quiet city should already be interesting before a warning runs.

The local frontend skill informed the emphasis on one dominant workspace, restrained chrome, deliberate motion and progressive detail. WorldBox supplies reference principles, not a template or asset source.

## Primary references and limits

| Reference | Evidence used | Direct media where available |
|---|---|---|
| [Official WorldBox website](https://www.superworldbox.com/) | Its central proposition is a world filled with life that can be changed through disaster powers. | [Official hero image](https://www.superworldbox.com/img/1600x655.png); the page also embeds an official trailer and gameplay clips. |
| [Developer's Steam store page](https://store.steampowered.com/app/1206560/WorldBox__God_Simulator/) | Creator/observer sandbox, creatures with traits and needs, civilization growth and world interaction. | Use the store's own gallery/trailer as the full-world reference. |
| [Publisher's Steam news/showcases](https://steamcommunity.com/app/1206560/allnews/?l=english) | Released ArmyBox showcases and a separately labeled upcoming Meta Control preview. Useful for selection, contextual tasks, map layers and HUD organization. | [R1: settlement, coastline, selection overlays and bottom HUD GIF](https://clan.fastly.steamstatic.com/images/39496096/e72f427c09c562b5662bf6b0bac8b6a112c2a9ca.gif); [R2: selected-unit task bar GIF](https://clan.fastly.steamstatic.com/images/39496096/4c34dcb07339f9d3330a857e86c57262123ee7d1.gif); [R3: in-world statistics panel GIF](https://clan.fastly.steamstatic.com/images/39496096/ce0e0163581ad77fb24aacd336a5695f8ffb49cc.gif). |
| [Official changelog](https://www.superworldbox.com/changelog) | Explicit records of unit walking-animation fixes, changing tornado graphics, burned-tree variants, night intensity, selected-unit status, minimap readability and optional borders. | This is written behavior evidence, not a source for implementation internals. |

R1–R3 were opened from the official publisher media host and visually inspected in a separate Chrome research tab; that tab was closed afterwards, restoring the simulator. No reference asset was downloaded into the application. Some web text tools cannot render GIFs, so browser inspection was used instead.

The news page mixes shipped releases and future previews. Treat the upcoming control/fog-of-war material as reference concepts, not proof that every pictured capability is released. The changelog supports night/age lighting controls; it does **not** establish a conventional 24-hour day/night cycle. This study does not infer WorldBox's engine, engine version, renderer, tile dimensions, shader code, sprite atlas organization or production pipeline from its appearance.

## What makes it recognizable

These are visual readings of the linked publisher images; the adaptation column is an original design proposal.

| Priority | Concrete observation | Last Warning adaptation |
|---|---|---|
| 1 | R1 is a continuous ground plane, with a settlement nestled among forest and shore. The environment is the composition, not a viewport surrounded by a website. | Make the city the application background. Keep a single slim HUD and a contextual inspector; remove the persistent website header/sidebar composition. |
| 1 | R1 uses tiny upright inhabitants, repeated huts, trees and fields at clearly different scales. | Read pedestrians as people, houses as shelters/addresses and larger landmarks as orientation anchors. Dense detail should reward zooming rather than enlarge every object. |
| 1 | R1 has stepped coast contours, shallow/deeper water bands and clustered vegetation. | Give Riverside a coherent riverbank, landscaped edges and neighborhoods; avoid a uniform colored square beneath isolated blocks. |
| 1 | R1's bottom edge is a compact, illustrated toolbelt with related commands grouped together. | Use original pixel icons and a modern emergency-console palette for observation, warning, disasters, time, history and advanced tools. |
| 2 | R2 puts a portrait, current task and important state next to a selected subject. | Clicking a resident should reveal their actual action, reason, time, goal and route, while the city stays visible. |
| 2 | R1 separates ordinary world detail from conspicuous selection colors; R3 keeps detailed statistics inside contextual game chrome. | Show identity with clothes/skin, attention with a small marker and selection with one outline. Keep charts, costs and model details behind a compact inspector. |

The transferable effect is scale plus activity plus context. A pixel filter over the present 3D scene would retain the same sparse blocks and website framing; it would miss most of what makes the reference compelling.

## Original visual system

### Camera and pixel discipline

- Prefer a near-overhead, orthographic world with upright sprites and consistent short ground shadows. Preserve the map's easy-to-read street geometry. This is a proposed Last Warning camera, not a claim about WorldBox's implementation.
- Explore one approved city vignette before selecting a renderer. A crisp sprite/tile renderer or an orthographic WebGL sprite scene could both work; choose based on readability, picking, zoom and measured frame time. Reusing Three.js is an option, not a reason to preserve the current floating-diorama composition.
- Establish one original pixel grid: for example, 16-pixel ground microtiles, 12–16-pixel pedestrian height and 32–64-pixel neighborhood buildings at working zoom. These are proposed asset sizes. They should be tested against the current 40 × 40 simulation scale rather than treated as WorldBox specifications.
- Render to a controlled logical resolution with nearest-neighbor enlargement at the key viewing scales. Snap camera translations and thin lines so small features do not shimmer. Keep text and accessible hit targets readable independently of the art resolution.
- Use outline/dither sparingly. Avoid combining blurry normal-resolution fonts, emoji, smooth gradients and pixel sprites without an intentional division between world art and readable controls.

### Terrain, water and a modern city

Use an original palette: deep ink for instruments, warm off-white labels, amber for commands/warnings, river teal/blue, restrained vegetation greens, terracotta brick and desaturated asphalt. Danger colors belong to actual hazard/state overlays; they should not tint every ordinary resident.

Build a layered city rather than random decoration:

1. **Geography:** a readable river, shore edge, bridge approaches and land elevation cues. Add riverbank reeds, retaining-wall details and water texture inside the current serialized river cells. A beautiful new coastline that changes traversability is a world-model change, not a harmless reskin.
2. **Neighborhood grammar:** narrow rowhouses/shops near the old center, detached homes and gardens farther out, compact civic landmarks near shelter sites. Fit all footprints to the existing inaccessible parcels and road graph first.
3. **Street life:** continuous sidewalks, intersections, crossing markings, alleys/doorstep cues, trees in intentional clusters, bins, benches and signs. A few recognizable bus stops or a schoolyard can orient the viewer, but their gameplay functions must remain unclaimed until modeled.
4. **Landmarks:** distinct emergency refuges, two bridge silhouettes and a handful of original named district markers. Use shapes that remain identifiable when zoomed out; do not label every roof.
5. **Controlled repetition:** several roof/wall/yard variants from a shared kit, consistent materials and seeded placement. Detail should reinforce districts, not create white noise across every tile.

Match civilization-like density without copying medieval fantasy. This remains a contemporary emergency-warning city: civic buildings, brick shops, apartments, compact parks, marked refuges and everyday pedestrians. It needs no castles, race banners, magic hands or WorldBox names.

### Agents as inhabitants

Replace large abstract markers with original tiny people: readable head/body/legs, stable clothing variation and a modest contact shadow. Use a small sprite set with enough skin, hair and clothing variation to read as a population; identity must remain stable across baseline/alternative recordings.

Proposed motion grammar:

- Animate a short two/four-frame walk only when recorded position changes. Face the traveled graph edge. Keep feet near the actual ground position; do not wander between decisions for decoration.
- Idle can use a restrained pose/blink that does not imply another action. Preparation may use a small in-place bag/readying gesture only when the actual state/action permits it.
- Use a brief message marker for recorded delivery or notice and a share pulse for an actual share event. A pulse is an interface visualization, not simulated radio propagation.
- Evacuating residents follow the recorded route. Shelter arrival can use a small ring/pip transition; showing a person enter a building requires a real doorway/interior mapping first.
- An exposed resident should not become a corpse. The current model records exposure, not death or injury. Use a distinct restrained status marker/pose and explain it on selection.
- Show model reasons for the selected person or a small event feed, not hundreds of persistent thought bubbles. If no model choice is available yet, show the actual state without manufacturing one.

Zoomed out, aggregate visually without changing counts: smaller resident dots/silhouettes, neighborhood labels and optional density/exposure overlays. Zoomed in, show sprite detail and the selected resident's route. Large state-colored circles belong to an optional analysis layer, not the default world.

### Disasters transform the same place

| Hazard | Proposed visual treatment | Authoritative data constraint |
|---|---|---|
| Flood | Blue-green inundation, light foam at the current boundary, darker pooling, partially submerged road markings and flow flecks. | Draw affected/active cells and closures from frames. Current simulation has arrival/depth internally, but depth is not exported per cell; accurate water-height/submersion needs new frame data. Generic wave flecks alone are cosmetic. |
| Wildfire | A moving orange/cream flame front, low ember count, sparse dark smoke and a visibly charred footprint behind it. | Flames use `active_hazard_cells`; ash uses cumulative `hazard_cells`. Do not show every burned cell still flaming. Building destruction/health needs a building model; a colored footprint cannot prove a house collapsed. |
| Tornado | A compact layered pixel funnel, rotating flecks near the actual center, a readable shadow and a persistent debris swath. | Respect `started`, center, radius, active footprint and blocked roads. Decorative debris cannot imply new destruction or road closures. Disable screen shake by default/reduced motion. |

The hazard is the visual climax. Do not fill the screen with particles that hide residents or safe routes. Keep effects local, legible and pause/seek aware; a replay at the same tick must show the same physical state. Ambient particles can use a seeded visual clock and should freeze when paused or under reduced-motion settings.

### Daylight and atmosphere

Use a carefully art-directed default daytime scene, with coherent shadows, water highlights and a small amount of ambient motion. A separately labeled lighting preview could be cosmetic. A fast sunrise-to-night transition during a ten-minute recorded emergency would be misleading. If time of day is meant to change visibility, received information, traffic or agent behavior, add explicit scenario time/lighting semantics and backend perception rules first. Do not imply WorldBox's age-based lighting is a direct real-time day/night model.

## One game panel, including the rest of the website

Proposed desktop composition:

- **World:** almost the entire first viewport, without a white page frame. A small title/location label lives in a calm corner.
- **Top compact strip:** selected disaster, warning and one clear **Broadcast / Run** command. Status can reveal the actual backend phase while a run computes; do not animate fictional resident progress during a blocking provider job.
- **Bottom toolbelt:** observe/select, warnings, hazards, layers, saved experiments and Advanced. Integrate pause, speed, seek and elapsed time nearby, with enough separation to avoid accidental commands.
- **Context panel:** one collapsible floating/docked panel for either a selected resident, warning composition, comparison outcome or detailed model information. No permanent stack of chart cards competing with the city.
- **Comparison:** one in-world toggle. Preserve synchronized timelines; consider two world panes with one shared game HUD, or a clear baseline/alternative switch. Any wipe/overlay must distinguish actual two recordings rather than blend residents into invented positions.
- **History, Mini and budgets:** open as a coherent game journal/console overlay with the same original pixel-edge grammar. Use readable structured text for numerical artifacts, provenance and costs. Do not force dense technical tables into tiny pixel typography.

Adopt original chamfered/pixel-stepped panel edges, restrained inset surfaces and clear pressed/selected states. Avoid copying WorldBox's specific stone carving, border ornament, red-button art, icons or typography. Keep the modern emergency identity through its own palette, signs and tool silhouettes. Do not build a generic SaaS dashboard and place a sprite canvas inside it.

On small screens, collapse to one shallow toolbelt plus a bottom sheet. The city remains the first thing visible. Touch targets must remain large even when their artwork is small. Keyboard navigation, focus rings, Escape/back, tooltips and reduced-motion behavior are requirements of the same design, not a separate accessibility skin.

## Honest feature boundary and priority

| Priority | Work | Can be visual/UI only? | What would require backend work |
|---|---|---|---|
| P0 | Original coherent terrain/building/sprite kit; full-world composition; compact HUD; agent state/selection; real hazard frames | Yes, if geometry, counts, routes and event semantics remain unchanged. | Changing roads/river/shelters requires new world metadata, validation and replay versioning. |
| P0 | Clear walk/idle/state animation, roof/tree variety, shoreline texture, contextual journal | Mostly; bind everything semantic to actual recorded data. | Exact intermediate walking paths may need per-tick edge/substep recording where a resident travels two cells around a corner. Straight tweening can cut across a building. |
| P1 | Real homes, work sites and daily activity before the warning | No. Current people start at road-side doorstep nodes and hold/act there. A goal mentioning family/work is not a simulated household or workplace. | Building IDs, entrances, occupancy, destinations, schedules, indoor/outdoor state, route links and event/frame data. Preserve common initial conditions across comparisons. |
| P1 | Visible resident escape plans | Current shortest route can be displayed if it is serialized/reconstructed honestly. | Per-resident planned-route snapshots and decision context if the user should inspect actual alternatives, intent changes and destinations. Do not invent a path in the renderer. |
| P1 | Better fire damage/flood depth | Surface styling is possible, but physical claims need data. | Export depth/arrival and add building/vegetation damage states, with rules and metrics. |
| P2 | Cars, buses, congestion and pickup/rescue | Parked cars may be scenery if clearly noninteractive; moving traffic should not impersonate simulated agents. | Vehicle agents, lanes, speeds, capacities, road/bridge interaction, boarding and occupied-person accounting. |
| P2 | Behaviorally meaningful night, smoke visibility or indoor sheltering | No. | Scenario clock, visibility/perception, health/exposure or shelter occupancy semantics and tests. |

Current Bedrock actions remain `WAIT/PREPARE/SHARE/EVACUATE`, evaluated at four epochs, with NetworkX routes and Mesa physical movement. A lively-looking idle scene cannot be used to claim continuous per-frame AI decisions. Mini is independent warning inference; it does not provide pedestrian animation, emotions or hidden thought states.

## Execution plan and visual acceptance

1. **Lock one original vignette.** Produce a small river-neighborhood art board with houses, three people, trees, one refuge, water and one compact HUD. Check daytime, flood and fire states before expanding to the whole map. No runtime migration is justified until the art language works at actual display size.
2. **Build the world treatment.** Apply the kit to the existing map and selected saved recordings. Keep the current physical model and data contracts intact while replacing the visual composition.
3. **Move all controls into the game frame.** Convert warning composition, Advanced, history, Mini and comparisons together so no leftover SaaS page appears when opening a secondary feature.
4. **Add truthful microanimation and feedback.** Bind movement, alert, share, shelter and hazard cues to recorded transitions. Verify pause, reverse seeking, restart and reduced motion.
5. **Only then expand behavior.** Houses/routines, exported routes, vehicles and time-dependent perception are separately scoped backend upgrades with explicit model/schema versions and tests. Art must not conceal their absence.

Acceptance should include: an engaging ten-second quiet-city recording; a 300-resident emergency readable at overview and street zoom; the same recognizable city under all three hazards; crisp pixels without jitter; legible agents over both grass and roads; a selected person's actual model action/reason/route; one-screen control hierarchy; no horizontal overflow at phone width; smooth pan/zoom measured on the target Mac; no false movement through parcels; and saved replay/compare fidelity. Use the real verified runs for evaluation before spending on additional model calls.

WorldBox logos, sprites, audio, UI ornament and named characters remain reference material only. All production assets, icons and branding for this direction should be original or separately licensed with recorded provenance.
