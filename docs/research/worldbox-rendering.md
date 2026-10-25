# WorldBox-inspired renderer: technical decision memo

Research checked **24 October 2026**. This is a plan, not an implementation or benchmark. No packages were installed, app behavior changed, or AWS/model calls made.

## Recommendation

Use **PixiJS 8 with authored top-down pixel sprites and tile atlases**, retaining React/TypeScript for the application and FastAPI/Mesa/Bedrock/local TRIBE Mini for its existing work. Start with one Pixi application, one canvas/context, one playback clock, and two clipped world containers for comparison. Reuse atlas textures between those worlds. This recommendation is an engineering judgment about fit, not a measured speed advantage.

Pin a compatible release set during implementation rather than installing floating latest versions. Current primary release sources report **pixi.js 8.22.0**, **@pixi/react 8.0.5**, and **@pixi/tilemap 5.0.2**. Pixi React 8 targets React 19, matching this repository; tilemap 5 targets Pixi 8 and its package requires Pixi >=8.5.0. Use a small compatibility spike before committing the production lockfile. [Pixi release](https://github.com/pixijs/pixijs/releases/tag/v8.22.0), [React binding release](https://github.com/pixijs/pixi-react/releases/tag/v8.0.5), [React 19 support](https://pixijs.com/blog/pixi-react-v8-live), [tilemap package](https://github.com/pixijs-userland/tilemap/blob/main/package.json).

## Options compared

| Option | Relevant capability | Fit and migration cost |
| --- | --- | --- |
| **PixiJS + @pixi/react + @pixi/tilemap** | GPU sprite renderer, rectangular tile batching, React scene binding; tilemap examples cover WebGL and WebGPU. | Best fit for an existing React simulator that needs a different visual world, rather than another simulation engine. React owns controls; Pixi owns sprite transforms, animation and picking. [Binding](https://react.pixijs.io/getting-started/), [tilemap](https://github.com/pixijs-userland/tilemap). |
| **Phaser 4.2.1** | Current stable archive release; built-in cameras, tilemaps, input, animation and explicit pixel-art settings. | Credible second choice if the product is becoming a game with editor tools, inventory and gameplay scenes. Here it adds a second scene/lifecycle framework around an already implemented Python simulation. Disable its physics for recorded residents. Phaser 4 has a new renderer; do not copy Phaser 3 pipeline assumptions. Its API site currently labels pages 4.1.0, so verify against pinned 4.2.1 source. [Release archive](https://phaser.io/download/archive), [4.0 renderer changes](https://github.com/phaserjs/phaser/blob/master/changelog/v4/4.0/CHANGELOG-v4.0.0.md), [camera system](https://docs.phaser.io/phaser/concepts/cameras), [4.2.1 pixel-art configuration](https://github.com/phaserjs/phaser/blob/v4.2.1/src/core/typedefs/RenderConfig.js). |
| **Godot Web 4.7.2** | A full authoring engine with 2D tools; current stable is 4.7.2, while 4.8 is beta. | Good for a separate game application, costly for this React site. Web export brings WebAssembly and a JS bridge, uses Compatibility/WebGL 2 rather than Forward+/Mobile/WebGPU, and has mobile constraints. The default single-thread export avoids thread-related isolation headers; that is not a performance guarantee. [Archive](https://godotengine.org/download/archive/), [web export constraints](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html), [JS bridge](https://docs.godotengine.org/en/stable/tutorials/platform/web/javascript_bridge.html). |
| **Existing Three.js + pixel postprocessing** | The repository uses Three 0.186.1; `RenderPixelatedPass` provides pixelated rendering with edge controls. | Lowest adapter churn, but preserves the underlying 3D model's silhouettes and depth. It is useful for a pixelated 3D art direction, not a substitute for authored WorldBox-style terrain, characters and tiles. Additional render targets/passes must be budgeted. [Official pixel pass](https://threejs.org/docs/pages/RenderPixelatedPass.html). |

For Pixi, prefer WebGL initially, with WebGPU treated as an independently tested option. Its application supports async initialization, renderer preference, resolution and multi-view configuration; the presence of those APIs does not establish browser/plugin compatibility or speed. A single canvas with rectangular clipping avoids depending on multi-canvas behavior for the first comparison implementation. [Application options](https://pixijs.com/8.x/guides/components/application).

## Preserve the simulation contract

The current `frontend/src/types.ts` and `backend/app/simulation/world.py` expose a **40 × 40 logic grid**. Roads are graph nodes; the river occupies columns 18–20, crossed at road rows 9 and 27. Shelter coordinates come from the scenario, including extra tornado shelters. Frames contain residents as `[id,x,y,state,exposure]`, affected cells, currently active hazard cells, blocked roads, hazard metadata and recorded model decisions.

The visual adapter must preserve those positions and memberships exactly. A renderer swap must leave metrics, saved warning text, model provenance, Mini outputs, road connectivity and comparison initial-condition hashes unchanged. A painted curved river or new island cannot silently replace the actual river geometry.

Keep the **40 × 40 logic grid** separate from art resolution. Candidate scales using 16 × 16-pixel art tiles are:

| Art tiles per logic cell | Art grid / placements per ground layer | Source world | Use |
| --- | --- | --- | --- |
| **1 × 1** | 40 × 40 / **1,600** | **640 × 640 px** | Simple fallback with compact silhouettes and low terrain geometry cost. Larger roofs/trees can still span tiles. |
| **4 × 4** | 160 × 160 / **25,600** | **2,560 × 2,560 px** | Candidate first-slice scale: 64 source pixels per logic-cell width leaves room for curbs, doors, paths and shoreline detail. Test legibility and cost before choosing it. |
| **16 × 16** | 640 × 640 / **409,600** | **10,240 × 10,240 px** | Excessive as a default; adopt only with demonstrated art need and measured chunking/resource budgets. |

These are visual placements, not new simulated cells or necessarily unique textures. A 4 × 4 ground layer in both comparison views has 51,200 placements before overlays; that count alone proves neither acceptable nor poor performance. Batch/chunk tiles rather than making each a React component. Build the same river/bridge/block slice at 1 × 1 and 4 × 4, then choose using overview/detail legibility, character scale, paired-view frame timing and memory. The moderate scale is a candidate, not a mandatory whole-map asset commitment.

At 4 × 4, each logic cell maps to a fixed 64 × 64-source-pixel footprint; road nodes, bridge crossings, shelters and hazard membership retain their original coordinates. Art subtiles add no collision, routes, walkable space or hazard precision. Drawing a narrow sidewalk inside a road cell does not authorize moving a resident onto a different logical position.

Residents currently start on and navigate **road nodes**. Walking around homes, farming, swimming, rebuilding, resource gathering or wandering through wilderness requires new backend mechanics and a versioned recording contract. Do not fake free roaming in the renderer. The current contract also has no recorded heading; derive facing from known movement segments, retain the last facing when stationary, and use a neutral idle pose without such history.

## Proposed rendering design

**Layers and atlases.** Ground/water → roads and static shadows → building bases → residents and props sorted by foot position → roofs/foliage where needed → effects and selection. Use consistent sprite anchors at ground contact. Split tall objects where necessary for credible occlusion; temporarily fade a roof or outline the selected resident rather than moving a resident above it. Stable ordering resolves equal-foot-position ties. Pixi supports child sorting but cautions about sorting large collections, so sort only dynamic/overlapping layers, not every terrain tile. [Container ordering](https://pixijs.com/8.x/guides/components/scene-objects/container).

Use a small atlas set with padded/extruded edges and shared texture sources. Pool 300 resident sprites per world, update them through refs in one tick callback, and keep React state for discrete application events. Avoid 600 React state updates per animation frame; the React binding specifically warns about unstable tick callbacks and repeated rerenders. [useTick](https://react.pixijs.io/hooks/useTick/).

**Pixel camera.** Use nearest-neighbor texture sampling, no smoothing/AA, snapped camera translations and integer source-texel magnification in crisp detail modes. `roundPixels` rounds positions, not arbitrary zoom factors. Account for CSS pixels, backing-buffer resolution and device pixel ratio separately. Provide an overview and explicit detail zoom steps; a full-map fit at every screen size/DPR cannot simultaneously guarantee integer magnification and zero letterboxing. On mobile, choose a deliberate overview atlas/LOD or allow panning rather than silently promising pixel perfection at fractional scaling. Test DPR 1, 2 and 3. [Texture sampling](https://pixijs.download/release/docs/rendering.TextureStyle.html), [sprite pixel rounding](https://pixijs.download/release/docs/scene.Sprite.html).

**Recorded movement and replay.** The engine can traverse multiple road edges in one tick. Interpolating the two frame endpoints directly can cut across a building at a bend. Add optional, backward-compatible `agent_motion` records to each arriving frame, describing the transition from its predecessor:

```ts
agent_motion?: Array<{
  id: number;
  from_tick: number;
  to_tick: number;
  segments: Array<{
    from: [number, number];
    to: [number, number];
    start_offset: number;
    end_offset: number;
  }>;
}>;
```

Record each actual edge as the engine traverses it; never reconstruct a route in the browser. Offsets are monotone fractions in `[0,1]` of that recorded transition. Because the existing engine is discrete, these offsets are explicitly **presentation timing**, using a documented distance-proportional allocation rather than claiming measured physical crossing times. Validate segment continuity, first/last endpoint agreement with `agents`, and that each segment was a permitted edge when traversed. Keep existing `agents` endpoints as the source of truth. Stationary residents need no motion entry.

Animate along those segments and derive facing from the current segment, preserving turns. Snap on seek, restart, missing/invalid motion or nonadjacent frames. **Legacy recordings without motion snap between positions** rather than guessing a shortest path or drawing a diagonal shortcut. A later legacy optimization may interpolate a transition only when a single traversed edge is provable. Run walking frames only for recorded motion; freeze ambient and character animation on pause/reduced motion.

Convert pointer positions through the viewport/camera transform, pick resident foot hitboxes, and offer cycling/list selection for overlapping residents. Picking shapes are UI aids, never physical collision bodies. Keep keyboard camera controls and DOM inspector semantics.

**Disasters.** Animate water only over the real flood footprint; flames only on `active_hazard_cells`, with soot tied to the affected footprint. Position a tornado at its recorded center/radius and honor its started state; retain the recorded aftermath after it exits. Particles are presentation only, with a fixed pool and bounded screen coverage. No visual effect may change routes, hazard membership, exposure or model actions.

**Culling and GPU resources.** Use coarse terrain chunks, not per-pixel objects. Test `@pixi/tilemap` against cached static chunks and keep the simpler winner. Update only dirty hazard chunks. Culling is not enabled by default and may add CPU cost; it helps zoomed-in offscreen worlds, not a full-map view where everything is visible. Do not assume enabling it improves every device. Cache static content selectively, since cached textures consume memory. [Performance guidance](https://pixijs.com/8.x/guides/concepts/performance-tips), [culler](https://pixijs.com/8.x/guides/components/application/culler-plugin), [static texture cache](https://pixijs.com/8.x/guides/components/scene-objects/container/cache-as-texture).

For comparison, one renderer should own two masked world roots, 600 resident slots, one clock and shared atlas pages; camera transforms can be synchronized. Avoid two independent applications uploading duplicate atlases. Query capabilities once at startup; handle context loss and release old render resources on teardown. Browser/GPU limits vary, so do not hardcode a universal context count or maximum texture size. [Browser WebGL guidance](https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API/WebGL_best_practices).

## Acceptance gates, not performance claims

No candidate has been benchmarked in this research phase. The following are proposed release gates, to be measured with recorded data and no new model calls:

| Test | Proposed gate |
| --- | --- |
| Desktop M4 Mac, current Chrome and Safari, 1440 × 900 | Mean ≥55 FPS single world; ≥50 FPS for simultaneous 300+300 comparison; p95 rAF interval ≤25 ms after warmup. |
| Physical mobile Safari and midrange Android Chrome, 390 × 844 class viewport | Mean ≥30 FPS and p95 rAF interval ≤40 ms, including paired view; use an explicitly labeled lower-effect quality tier if required. An emulated viewport does not qualify as mobile GPU evidence. |
| Method | Warm up 5 s, measure 60 s, repeat three times for all three disasters; include full-map, integer zoom/pan, maximum recorded hazard coverage, comparison and a five-minute mobile thermal soak. Report the device, browser, renderer backend, resolution, distribution and worst case. |
| Interaction and resources | p95 selection response ≤100 ms after warmup; zero WebGL/JS errors; successful context restoration; no continuing resource growth across 20 open/close/comparison cycles. Paused worlds stop their animation ticker and redraw only for input/resize/data changes. |
| Art and correctness | No atlas seams, fractional-zoom shimmer in crisp modes, incorrect roof occlusion or hidden controls at target DPRs. Agent IDs/cells, hazard/closure sets, selected decision/reason/time and metrics match recordings exactly. Multi-edge bends follow recorded segments without corner cutting; ambiguous legacy transitions snap. Compare both proposed art scales on the same slice before committing. |

Initial **project budgets**, subject to measurement: four 1024² RGBA atlas pages are 16 MiB before other textures; keep total estimated GPU textures/targets below 128 MiB desktop and 96 MiB mobile, cap mobile back-buffer resolution, avoid full-screen blur/bloom, and pool effects. These are engineering budgets, not hardware guarantees. If gates fail, first reduce particle overdraw, filters and cache resolution, then tune chunking/culling. Do not remove residents or falsify their positions to reach a frame-rate number.

## Migration boundaries

1. Keep `CityMap`'s public props, selection callback and legend/state exports. Add `frontend/src/worldbox/` for `PixelWorld`, `CityVisualAdapter`, `PixelCamera`, `ResidentLayer`, `HazardLayer`, `ReplayClock`, selection and diagnostics. Implement a small art-complete river/bridge/block slice at the 1 × 1 fallback and candidate 4 × 4 scale before choosing the whole-map scale.
2. Add versioned atlas PNG/JSON files and a manifest under `frontend/public/art/worldbox/`, with licenses and explicit cell footprints/anchors. Keep application chrome and neural charts as accessible React/CSS; do not turn small explanatory text into unreadable canvas pixels.
3. Refactor only the map/comparison host in `App.tsx` for one canvas/two views. Keep warning CRUD, Bedrock orchestration, recorded reasoning, budgets and local Mini unchanged.
4. Change `frontend/package.json`, its lockfile and Vite chunks only after the compatibility spike. Keep the existing Three scene as a temporary rollback path, never an additional active renderer. Remove Three dependencies after recorded-data parity and target-device gates pass.
5. The visual-only fallback needs **no backend migration**. Faithful smooth multi-edge replay additionally needs the optional `agent_motion` writer in `backend/app/simulation/engine.py`, an additive frame type in `frontend/src/types.ts`, versioned recording semantics and path-continuity/legacy-reader tests. Keep old saved recordings readable; this does not itself require rewriting them or changing simulation outcomes. A later WorldBox-like living-world phase must separately define terrain generation, homes, free-space movement and collision/pathfinding, then version the simulation and revalidate comparisons. Frontend decoration cannot substitute for that work.
