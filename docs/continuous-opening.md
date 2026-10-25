# Continuous Earth-to-Oval opening

The opening now uses one continuous geographic scale: Earth → North America → Ohio → Columbus → Ohio State → the Oval. It rotates for 2.4 seconds, descends over 8.4 seconds with a smooth logarithmic scale curve, and settles for 350 ms. Slow world loading holds the globe before descent; Skip and Escape always exit.

## Camera and registration

The target is the actual `city.camera_focus`, converted back through the serialized campus geographic bounds. This corrects the previous approximate globe target, which was about 360 m northwest of the Oval. Metric projection coefficients come from `map_bounds`, `selection_bbox` and `meters_per_unit`.

At regional scales, the orthographic globe projection progressively becomes the same north-up metric projection used by the campus. Ohio boundaries, Great Lakes, Columbus roads/rivers and surrounding footprints resolve as scale increases. Terrain/roof styling is illustrative; geographic geometry is sourced.

At campus scale the opening drives **the live Pixi camera**, with continuous zoom instead of the ordinary discrete wheel-zoom levels. The context painter contains the same campus geometry beneath the live scene, with shared building palettes, road widths and mapped tree sprites. A broad, geographically anchored irregular alpha mask introduces native detail across the join. It does not cut a rectangular window into the context. Local context and live rendering use the same fine pixel density. No screenshot or whole-overlay opacity animation is involved. The final pose uses the ordinary camera's exact inset-aware, clamped transform, and stays there when the overlay is removed.

HUD elements remain laid out but hidden during the flight, so inspector insets cannot change just as controls return. The existing daily/replay clocks pause during the opening. Skip restores the prior camera, including follow/location state. A completed flight lands on the Oval. Split comparisons and non-campus worlds do not offer replay.

## Assets and limits

All context ships locally; no map service is called during playback. [Geography research and provenance](research/opening-geography.md) records Natural Earth and OpenStreetMap sources. Each bundled GeoJSON has a provenance manifest with hashes and the exact source query. Linked OpenStreetMap attribution remains visible throughout.

Surrounding footprints are decorative opening context, not an expansion of simulation geography, navigation or available shelters. States' administrative lake boundaries are covered by the actual lake polygons. Reduced-motion mode retains a static Earth and Enter campus; it does not move the live camera.

## Verification

- Ten camera regression checks pass (`node scripts/verify-opening-camera.mjs`), exercising actual camera methods, real serialized campus geography, continuous zoom, exact end transforms, resize, inspector insets, Skip/follow restoration and disposed/unsupported states.
- Eight geography checks verify shared campus registration, sourced surroundings, road continuity and level-of-detail behavior.
- Three geographic blend checks cover bounded coverage, irregular feathering and final detail resolution.
- Production TypeScript/Vite build passes; the existing Pixi chunk-size advisory remains.
- Desktop stage captures verify Ohio, Columbus, campus and Oval geography.
- Final desktop browser bounds match after rounding (maximum raw reporting difference 0.459 CSS pixels); camera-method tests confirm identical rendered transforms. Preview: `output/playwright/earth-to-oval-blended.webm`.
- Mobile normal playback has identical map bounds before/after opening removal. Skip and Escape restore exact previous pan/zoom and focus.
- Reduced-motion globe remains painted through portrait → landscape → portrait resizing. No application console errors appeared in these flows.

Opening sound is opt-in through More → Sound. Flight progress drives a restrained travel envelope; automatic landing has a short arrival cue. Skip, reduced motion, hidden tabs and cleanup stop the flight envelope. See [pixel sound design](pixel-sound-design.md).

The opening itself changes no simulation geography or AWS resources. Separate behavior corrections from the same audit are documented in [behavior fidelity](research/behavior-fidelity-audit.md).

### Seam and audio pass — October 25

The local surroundings include 2,252 mapped road-line pieces, 2,414 path pieces and 2,843 tree points outside the campus survey. Context detail resolves around the destination with a broad radial falloff; subpixel roads use a single clean stroke. Campus buildings, paths and trees continue beneath the live-detail feather. Browser captures at neighborhood and campus scales show the source rectangle removed.

The refreshed 390×844 mobile flight matches its final rendered camera bounds after ordinary pixel rounding; reduced-motion portrait/landscape resizing stays painted, and Escape returns keyboard focus to the world. Browser console: no errors. A desktop pacing sample of the local flight recorded 258 rAF observations, median 8.5 ms, 95th percentile 25.7 ms and maximum 34.9 ms; rAF includes the 120 Hz display callbacks, while drawing is capped at 60 Hz. This is one development-machine observation, not a performance guarantee.

The sound engine's eight regression checks and an actual UI integration pass cover opt-in, flight progress, exact arrival cue, Skip/Escape, mute persistence and the visibility handler. The handler was tested with a controlled hidden event; native tab-background state was unavailable in that browser session. See `output/playwright/audio-integration-results.json`.
