# Pixel city assets and skills research

Research snapshot: 24 October 2026. This is an implementation plan, not a claim that the assets have been produced. No tools or skills were installed, no assets were downloaded, and no paid inference or purchases were made for this research.

## Recommended direction

Build an original, top-down pixel city with the legibility and activity of a small simulation game. Use authored tiles and animation frames, a single palette, consistent foot anchors, and restrained UI around the world. WorldBox is a reference for the experience; its sprites, branding, and interface artwork are not source assets.

Use **Pixelorama → Tiled → PNG/JSON atlases** as the free default. An existing Aseprite license can replace Pixelorama. Keep the existing simulation grid and recorded events authoritative: art may decorate a road, shelter, hazard, or resident, but must not create a different road network or imply unrecorded agent decisions. Render physics positions continuously if needed, then snap their displayed positions to the chosen pixel grid.

Approve a small in-engine art sample before making hundreds of frames: one river crossing, four buildings, six props, a walking resident, and each supported disaster. Test it at the actual viewing scale. Do not accept a detailed contact sheet that becomes indistinguishable noise in the simulator.

## Skills examined

Discovery began with the [skills.sh leaderboard](https://www.skills.sh/). The following are **observed directory counts**, not independent adoption measurements or guarantees of quality. Counts on the leaderboard and individual pages differed slightly during research; the table uses the individual pages. Every linked upstream `SKILL.md` below was read, rather than relying on its name or installation count.

| Skill and inspected upstream source | Observed installs / repository stars | Useful application and limits |
| --- | --- | --- |
| [Anthropic frontend-design](https://raw.githubusercontent.com/anthropics/skills/main/skills/frontend-design/SKILL.md) | [1.0M / 183.5K](https://www.skills.sh/anthropics/skills/frontend-design) | Official publisher. Make the live city the visual focus; use a deliberate palette, quiet controls, and one or two typefaces. This guides composition, not sprite production. |
| [Vercel web-design-guidelines](https://raw.githubusercontent.com/vercel-labs/agent-skills/main/skills/web-design-guidelines/SKILL.md) | [780.2K / 33.0K](https://www.skills.sh/vercel-labs/agent-skills/web-design-guidelines) | Official publisher. Apply its [current interface rules](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md) to keyboard navigation, focus, labels, reduced motion, and usable controls around the canvas. |
| [OpenAI sprite-pipeline](https://raw.githubusercontent.com/openai/plugins/main/plugins/game-studio/skills/sprite-pipeline/SKILL.md) | [53 / 7.6K](https://www.skills.sh/openai/plugins/sprite-pipeline) | Official publisher, low observed adoption. Its [normalization workflow](https://raw.githubusercontent.com/openai/plugins/main/plugins/game-studio/references/sprite-pipeline.md) usefully anchors every frame to an approved seed, shared scale, and common foot position, then previews the strip in the game. Generation is optional; normalization is useful for authored art too. |
| [omer-metin pixel-art-sprites](https://raw.githubusercontent.com/omer-metin/skills-for-antigravity/main/skills/pixel-art-sprites/SKILL.md) | [2.7K / 179](https://www.skills.sh/omer-metin/skills-for-antigravity/pixel-art-sprites) | Community source, suitable as a checklist rather than an authority. Its [patterns](https://raw.githubusercontent.com/omer-metin/skills-for-antigravity/main/skills/pixel-art-sprites/references/patterns.md), [sharp edges](https://raw.githubusercontent.com/omer-metin/skills-for-antigravity/main/skills/pixel-art-sprites/references/sharp_edges.md), and [validation notes](https://raw.githubusercontent.com/omer-metin/skills-for-antigravity/main/skills/pixel-art-sprites/references/validations.md) cover limited palettes, readable silhouettes, short walks, atlas bleed, and uneven pixel scaling. Confirm renderer advice against primary documentation and screenshots. |
| [PlayableIntelligence game-assets](https://raw.githubusercontent.com/PlayableIntelligence/game-creator/main/skills/game-assets/SKILL.md) | [1.6K / 346](https://www.skills.sh/playableintelligence/game-creator/game-assets) | Useful secondary guidance for a sprite inventory, silhouettes, and replacing generic geometry with recognizable art. Its code-matrix, celebrity, and meme-oriented examples do not fit this project. Borrow the review principles, not the complete workflow or example characters. |

Dedicated community pixel-art skills exist; none inspected provides a mature, first-party pixel-art production system that can be assumed to make finished art automatically. The strongest combination is official composition/accessibility guidance, explicit asset normalization, and an authored art review. The low install count of the official sprite skill is disclosed rather than disguised as broad adoption.

Already available locally: `frontend-skill` for the visual brief, `find-skills` for discovery, `Playwright` for browser verification, and `imagegen` for optional concepts. Image generation can supply references or a draft strip, but does not establish clean pixel clusters, uniform animation, or production readiness. No additional installation is needed to apply the researched guidance.

## Authoring and packing tools

| Tool | Decision | Benefits and tradeoffs |
| --- | --- | --- |
| [Pixelorama](https://pixelorama.org/) | Default sprite editor; free and open source | Indexed palettes, onion skinning, frame tags, tilemap layers, spritesheet export, and command-line export support. Store editable sources as well as exported PNGs. It avoids a purchase for this phase. |
| [Aseprite](https://www.aseprite.org/docs/cli/) | Preferred substitute if already owned | Batch PNG/JSON export, tags, slices, padding, and extrusion make a reproducible pipeline practical. The [official FAQ](https://www.aseprite.org/faq/) currently lists a USD $19.99 minimum for its convenient binaries; optional purchase, outside AWS credits, with checkout/tax to confirm if ever bought. |
| [Tiled](https://www.mapeditor.org/) | Default tileset/composition editor | Free and open source, with JSON export and [terrain brushes](https://doc.mapeditor.org/en/stable/manual/terrain/). Use it to test tiles and author decorative layout against the real simulation map. A two-terrain edge/corner set can use 16 tiles; a complete mixed set is larger, and the common reduced blob set has 47. Do not assume 16 tiles cover every shoreline junction. |
| [LDtk](https://ldtk.io/) | Alternative to Tiled, not an additional required editor | Free, with JSON and simple PNG/JSON export; auto-layers and direct Aseprite reload can accelerate controlled variation. Introduce one map format, not two competing importers. |
| [TexturePacker](https://www.codeandweb.com/texturepacker/documentation/installation-and-licensing) | Optional later; no purchase recommended now | Strong atlas tooling, but its free trial and noncommercial Essential mode should not become a hidden runtime/build dependency. [CI licensing](https://www.codeandweb.com/texturepacker/documentation/docker-ci) is separate. A single-user checkout price was not verified, so no price or paid-tool budget is assumed. |
| [Free Texture Packer source](https://github.com/odrick/free-tex-packer) | Exclude from the default toolchain | MIT source, but the maintainer states improvements are paused except critical fixes; published desktop releases are old. During this check, its former website redirected to a parked domain. Use the reviewed repository as the reference, not that domain or its downloads. |

Export an ordinary grid sheet directly from the chosen art editor first. Only add a packer when measured texture waste justifies it. For tiny sprites, initially disable atlas rotation and trimming; stable cell rectangles and foot anchors are easier to audit. If later packing trims frames, preserve the original logical dimensions and offsets in metadata.

## Asset sources and licensing

[Kenney Tiny Town](https://kenney.nl/assets/tiny-town) is a useful optional foundation: 130 files, 16×16 style, CC0. Kenney's [official support page](https://kenney.nl/support) confirms that asset-page downloads can be used commercially without mandatory attribution; the Kenney logo has separate restrictions. Choose one coherent source pack, then extend or repaint it into this city's palette. Do not combine unrelated packs merely to increase asset count.

LPC/OpenGameArt is not blanket public-domain material. The original [LPC style guide](https://lpc.opengameart.org/static/LPC-Style-Guide/build/index.html) describes CC-BY-SA/GPL licensing for its art, and individual [OpenGameArt collections](https://opengameart.org/content/liberated-pixel-cup-0) require per-asset inspection. Its larger character conventions also cost space and stylistic consistency here. Prefer original artwork or the clearly identified CC0 pack for the initial release.

Record provenance for every external source even when attribution is optional: source page, author, exact downloaded version, license, modifications, and checksum. Keep any required credit/license text beside the distributed assets. A skill's repository license does not license artwork that the skill happens to mention.

## Proposed authored asset inventory

These are planning quantities, not existing deliverables. Start with a 16×16 terrain unit, residents approximately 8–12 pixels wide by 12–16 high, and buildings that occupy multiple art cells. Confirm these sizes in the sample before locking the manifest. Keep one light direction, three or four deliberate shade steps per material, compact pixel clusters, and a common palette of roughly 24–32 opaque colors plus transparency. These are project art constraints, not claims about WorldBox's internal assets.

| Group | Proposed source frames | Contents |
| --- | ---: | --- |
| Terrain and transport | 83 | 12 base/variation tiles, 47 shoreline tiles, 16 road connection masks, 8 bridge pieces |
| Buildings and damage | 32 | 24 distinct house/shop/civic/shelter silhouettes, 8 reusable damage overlays |
| Props and vegetation | 24 | Trees, shrubs, lamps, fences, benches, vehicles, signs; a controlled mix of repeated and landmark pieces |
| Residents | 56 | Two base silhouettes × four directions × four walking frames = 32; eight idle poses; eight preparing and eight sharing poses. Approved palette variants add variety without changing anatomy frame to frame. |
| Disaster effects | 32 | Four water, six fire, six smoke, eight tornado, four debris, four alert/signal frames; only effects relevant to recorded simulation state are shown |
| UI symbols | 16 | Small original action/disaster/transport symbols; readable text remains normal UI typography |
| **Total** | **243** | Shared modular frames, not 243 unrelated illustration prompts |

The full inventory follows a vertical slice, not the reverse. Add new variants only after the primary shelter, bridge, resident, and hazard silhouettes are distinguishable at the normal zoom. The same resident must remain identifiable when walking, preparing, sharing, and evacuating. Keep danger status and selected-resident outlines outside the sprite palette so overlays do not recolor its body unpredictably.

An asset manifest should record: `id`, category, source file, atlas rectangle, logical size, foot anchor, simulation footprint, drawing layer, animation tag, frame durations, loop behavior, palette version, provenance/license, export-tool version, and checksum. Preserve editable `.pxo`/`.aseprite` sources. Produce separate terrain/building, resident, and effect atlas groups only when their loading/filtering behavior benefits from separation; do not promise an arbitrary final atlas size before measuring the sample.

## Acceptance gates before shipping

1. **Pixel fidelity:** nearest-neighbor sampling, no JPEG, no unintended antialiased edges, no atlas neighbor bleed, and no per-frame scale drift. Check native scale and discrete 2×/3×/4× views. Test browser zoom and DPR 1/2 explicitly: CSS `image-rendering` alone does not guarantee evenly sized physical pixels. Use the [MDN pixel-art guidance](https://developer.mozilla.org/en-US/docs/Games/Techniques/Crisp_pixel_art_look) and real rendered screenshots.
2. **Animation quality:** four walk frames read as walking at normal scale; feet remain anchored through loops; frame durations are explicit; pause and reduced-motion settings stop ambient movement. No independently generated frames with changing clothes, anatomy, or outline weight.
3. **World integrity:** roads, bridges, shelters, blocked paths, hazard extents, and resident positions agree with backend data. Damage decoration never invents a casualty or a model decision. The same stored replay produces the same visible world state.
4. **Visual hierarchy:** the city is the main focus; ordinary movement, evacuation, danger, shelter, and selection are distinguishable without relying only on red/green. Labels stay legible and controls remain operable by keyboard. Test crowded 300-resident scenes rather than only a sparse art sample.
5. **Production hygiene:** atlas metadata validates against image bounds; every animation has all frames and a consistent anchor; no orphan assets, missing licenses, external hotlinks, or editor/trial dependencies in the shipped runtime. Keep a before/after screenshot contact sheet and a short captured replay for approval.
6. **Scope and cost:** approve the sample first, then terrain/buildings, residents, effects, and UI detail in that order. Use the free toolchain by default. Asset-authoring purchases and optional image-generation costs are explicit future choices, not hidden inside the AWS project budget.

The main quality risk is not finding an editor or another skill. It is allowing several incompatible palettes, pixel scales, source packs, and animation anchors into the same world. A small approved art bible, editable sources, a provenance manifest, and repeated in-engine review address that risk directly.
