# Building discovery and pixel rendering polish

The October 24, 2026 pass addresses building identification, fragmented character artwork and rough street/path joins. The world remains the primary workspace: one short building card appears on demand, with search and resident access available without a permanent layer of labels.

## Building names

- All 937 mapped footprints can be identified independently of occupancy. The 217 source names remain intact; unnamed buildings use existing place names or a building-type fallback, not invented official names.
- Desktop hover shows one quiet name/type/occupancy card. Clicking or tapping pins it and exposes the residents inside. Direct person/car picking remains available.
- The magnifier searches building names and contained venues. Query words match independently, so “Thompson Library” finds “William Oxley Thompson Memorial Library.” Enter focuses the first match; Escape dismisses the card/search.
- Roof lift, visible walls and courtyard holes are included in picking. The scenery painter and label index share height/classification helpers. Occupants or vehicles hidden behind a roof do not win the building click.
- Pan, zoom, resident selection and event-origin placement clear discovery. Mobile cards and search avoid the header and playback dock. The warning brief temporarily clears space while discovering a building.

## Characters

The old gait moved arm outlines separately from their sleeve/skin fills, profile views retained front-facing details, and isolated highlights produced noisy silhouettes. The new drawing uses registered limbs, contiguous color clusters, complete directional poses and a quieter palette. Seeded combinations of hair, clothing, body proportions, bags, headwear and mobility aids remain generated. Children now have native geometry instead of an additional fractional shrink.

Close camera zoom aligns to backing-device pixels; overview can still fit the map. Nearest sampling stays enabled. Static map labels wait for their pixel font before rasterization, preventing a cold-load fallback font from being permanently baked into scenery.

## Streets and paths

The former surface pass gave service lanes near-street widths, drew entrance links as broad walks, rounded source vertices to a different grid from their antialiased edges, and drew independent outlines through plazas and across roads.

The corrected renderer rejoins consecutive fragments of the same mapped way, preserving clipped gaps. Pedestrian plazas and lines form one surface. Local access lanes and doorway connectors have narrower widths. Roads remain continuous through pedestrian crossings, with quiet curbs and uninterrupted curved edges; dashed road centerlines clear junctions. No new road/path connections are introduced. The real Oval's radial and diagonal paths remain intact.

## Verification

- Production TypeScript/Vite build passed; the existing Pixi bundle-size advisory remains.
- `node scripts/verify-campus-building-labels.mjs`: seven tests passed, including real-map identity/name preservation, empty buildings, raised roofs/facades, courtyard exclusion and depth precedence.
- `node scripts/verify-campus-surfaces.mjs`: four tests passed, including exact conservation of 2,956 road and 8,264 kind-qualified pedestrian segments, no linking across gaps, and reversed-duplicate removal.
- Character audit: 300 distinct seeded recipes × four directions × eight poses = 9,600 frames, with no unintended alpha pixels, atlas edge bleed or east/west profile mirror mismatch. Evidence: `output/character-polish-verification.json`.
- Desktop and 390×844 mobile browser checks covered search, hover, pin/tap, empty buildings, resident access, Escape/close, pan/zoom dismissal and layout. No browser errors, horizontal overflow or header/dock collisions were observed.
- No new model inference, cloud resources or paid requests were needed. Simulation schedules, routing and hazard logic were not changed in this visual pass.

Proof images are under `output/playwright/`: `character-polish-contact-sheet.png`, `campus-building-hover-desktop.png`, `campus-building-search-desktop.png`, `campus-building-mobile.png`, `campus-building-mobile-empty.png`, `campus-path-polish-oval.png`, `campus-path-polish-curve-detail.png`, and `campus-path-polish-neighborhood.png`.
