# Pixel world renderer

`CityMap.tsx` preserves the existing simulator interface. `PixelComparison` shares one Pixi/WebGL canvas, clock, camera, atlas and terrain texture between two clipped views. React owns controls and inspector state; pooled Pixi objects own rendering.

- `Art.ts`: cached original atlas loading, palette/appearance lookup and pixel drawing.
- `CityVisualAdapter.ts`: static 2560×2560 terrain/architecture texture assembled from actual road/river masks. Source art resolution is four 16-pixel tiles per 40×40 logic-cell edge. Shelter markers are separate per-view data.
- `OrganicTown.ts`: new canonical winding-road/path/bridge and meandering-river art. Named places use their actual footprint and entrance; the old grid renderer remains the fallback for older recordings. Facades stay upright.
- `ResidentLayer.ts`: stable resident ID/seed appearance, feet picking and recorded path playback. Missing/invalid legacy paths snap. No route is inferred in the renderer.
- `TownAtmosphere.ts`: lighting from recorded world-clock minutes, occupied-place indicators and recorded interaction bubbles. Inside residents hide at the end of their actual arrival motion. Clicking an occupied footprint cycles its actual indoor residents; the marker uses the recorded entrance and does not invent an interior position.
- `HazardLayer.ts`: affected footprints, active flames/water, recorded tornado geometry and actual closure barriers. Effects never modify model outcomes.
- `WeatherPresentation.ts` / `WeatherLayer.ts`: recorded physical seconds drive cloud cover, rain, hail, wind and event-timed lightning. Screen-density precipitation stays readable at every zoom, inside each comparison mask. Exact frame endpoints use the saved active flag; interpolation uses the recorded active window. Paused frames freeze effects, seeks suppress historical flashes, and reduced motion retains static weather without lightning flashes.
- `WeatherSurfaces.ts`: cached snow blankets the ground, mapped roofs and tree canopies in twelve accumulation stages. Paths remain readable and water stays uncovered. Coverage is illustrative, not a measured snow depth or a plowing model; it persists after the snow stops. Snow caps participate in the same depth ordering as buildings and residents.
- `TornadoVisual.ts`: a connected, stepped funnel with an irregular cloud crown, rotating highlights, ground dust and airborne debris. The large aerial silhouette is presentation art; the ground-contact footprint still uses the recording's exact center and radius.
- `ReplayClock.ts`: shared interpolation progress and effect time, exact pause/resume, reduced motion.
- `PixelWorld.ts`: lifecycle, masks, synchronized camera, follow-state notification, mouse/touch/keyboard controls, context restoration and on-demand paused redraw.

Original art source and provenance: `frontend/art/last-warning/`. Runtime art: `frontend/public/assets/art/last-warning/`. There are no paid asset or model calls in renderer loading/replay.

Camera: drag to pan, pinch/wheel or +/− to zoom, arrows to pan, Home/0 for overview, F to follow a selected resident. Repeated clicks cycle through residents sharing a hit area. Buttons and hit areas remain usable around the small sprites. Fractional overview scaling is intentional; nearest sampling and detail zooms preserve the authored edges.

Desktop smoke measurements and correctness evidence live in `output/playwright/pixel-renderer-verification.json`. Mobile viewport screenshots demonstrate layout only; physical mobile GPU/Safari performance is not established by those captures.

Weather verification: `node --test scripts/verify-*.mjs` includes timing, surface geometry, tornado silhouette, seek/pause, audio and comparison regression checks. `output/weather-render-fixtures.json` contains 25 offline hazard snapshots over the sourced campus with fixed sampled residents, explicitly for atmosphere QA. These fixtures are not new Bedrock runs. Saved Bedrock storm and blizzard recordings are also checked through the real simulator UI. Thunder audio follows recorded thunder timestamps across coarse frames and remains opt-in.
