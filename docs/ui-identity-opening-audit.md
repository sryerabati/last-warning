# UI, identity and opening audit

## Delivered

The simulator remains one page. Immediate actions stay beside the world; secondary tools are organized into **World**, **Analysis**, **Reference** and **Preferences** under **More**. Sources & methods has separate Simulation, Evidence and Models sections. Details such as token accounting, model IDs and provenance are expandable rather than repeated in the main interface.

All live React controls now use the same readable 16×16 pixel icon family. Sound uses a speaker; results use a chart; reference material uses a book; warning editing uses a pencil. Route display, camera following, hazard placement, previous/next residents, playback restart and return to town have distinct symbols. A busy warning button uses a loading indicator rather than a pause symbol. The browser favicon matches the pixel beacon. Text labels and accessible names remain authoritative.

The full icon/action matrix and information-architecture findings are in [the icon audit](research/ui-icon-ia-audit.md).

## Fictional residents

The default 300-person cast now has 300 distinct full names instead of 207. Families share coherent names and seeded visual resemblance; roommates keep independent identities. Natural hair dominates, dyed colors are occasional, and children no longer receive gray hair. A short fictional biography is available beneath **About [given name]** in the inspector.

Names do not determine skin tone. Cross-cultural and preferred given names remain possible. The generation rules are authored character-design choices, not measured OSU demographic distributions. Names, appearance and biographies are excluded from new campus Bedrock decision contexts; the model receives neutral resident identifiers. Historical recordings preserve their original context and appearance.

Homes, schedules, social contacts, walking speeds, mobility, goals and trust were preserved: a before/after hash over all operational profile fields is identical. Identity and engine versions changed to distinguish new recordings. See [the identity audit](research/campus-identity-audit.md) for evidence and boundaries.

## Opening

The initial globe-to-campus dissolve was replaced by a [continuous Earth → Ohio → Columbus → Oval camera flight](continuous-opening.md). The final approach drives the live world camera. Coastlines, states, lakes and local context come from pinned Natural Earth/OpenStreetMap assets; terrain and roof styling remain illustrative. No new runtime dependency, remote asset request or audio autoplay is needed.

- Normal warm playback now takes approximately 11 seconds and runs once per browser session.
- **Skip opening** and Escape exit immediately. Keyboard focus stays within the opening, then returns to the world or its loading container.
- Reduced-motion preferences bypass the automatic animation. **More → Replay opening** presents a static globe with **Enter campus** in that mode.
- The detailed globe holds while campus prepares, rather than zooming into an empty scene. A map error releases the hold so the error remains accessible.
- A failed/expired geometry fetch exits safely. Its rejected promise is cleared so later replay can retry successfully.
- The town clock and recording playback pause during the opening; the animation does not call Bedrock or TRIBE.

Implementation: `frontend/src/pixel-ui/CampusOpening.tsx`. Asset provenance: `frontend/public/assets/geography/natural-earth-land-110m.provenance.json`.

## Evidence and next improvements

The Evidence section contains five dated entries: OSU enrollment, academic calendar, CABS service, Columbus climate normals and NWS severe/destructive storm thresholds. Each carries a source, period, scope, current use and limitation. Enrollment/calendar/transit/climate references are explicitly context only; they have not been silently converted into behavioral calibration.

The most useful next work is calendar-aware day types, actual CABS boarding/routes/capacity, and seasonal clothing/ambient presets. Those features need their own state transitions and validation. Aggregate household/vehicle calibration requires a defensible census geography crosswalk before importing numbers. See [the evidence refresh](research/campus-evidence-refresh.md) for primary links and a bounded modeling backlog.

## Verification

- Backend: **263 tests passed** in 183.25 seconds, using mocked provider boundaries and temporary storage. One existing FastAPI/Starlette test-client deprecation warning remains.
- Ruff: `backend/app` and `backend/tests` pass. A broader scan also reported seven existing lint issues in unrelated AWS/TRIBE launcher scripts; those scripts were not changed by this audit.
- Production TypeScript/Vite build passes. The existing Pixi bundle-size advisory remains.
- Desktop browser: new resident names and biography, normal opening and arrival, correct menu destinations, and underlying-world inert state verified.
- Mobile at 390×844: More menu and Sources panel fit without horizontal overflow; evidence details and panel close remain reachable. Opening Skip is at least 44px tall and stays within the viewport.
- Accessibility: opening focus, Tab containment, Escape, normal completion, reduced-motion bypass/static replay, and focus restoration verified.
- Static reduced-motion rendering survives portrait → landscape → portrait changes. A ResizeObserver issue that cleared the canvas after its one static frame was fixed and visually rechecked.
- Resilience: a deliberately failed globe request exits; the next replay fetches successfully and opens. No unexpected console errors were found in the verified flows.
- User's existing simulator tab refreshed to the new build; authenticated server process preserved.

No paid model inference, cloud provisioning or schema migration was required. These checks do not constitute new Bedrock or TRIBE inference results or scientific validation of synthetic behavior.

Visual evidence is under `output/playwright/`: `campus-opening-earth.png`, `opening-normal-mobile.png`, `opening-reduced-mobile.png`, `opening-reduced-landscape.png`, `resident-identity-inspector.png`, `sources-evidence-mobile.png`, `sources-menu-mobile.png` and `pixel-icon-audit.png`.
