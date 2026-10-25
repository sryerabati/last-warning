# Campus character artwork

The campus renderer uses original, modular 32 × 48 pixel art inspired by the
approved living-diorama direction. It does not select from twelve finished people
or ask an image model to redraw residents while the simulation runs.

`CharacterDesign.ts` is the editable part library and compositor. A saved
appearance recipe independently selects body shape, eight skin tones, eight hair
colors, eight hairstyles, six garments, twelve top colors, eight trouser colors,
seven accessories and five headwear choices. Age and mobility are also retained.
The API validates every numeric choice. Missing fields use an independent seeded
hash of the resident ID and world seed; behavior, trust and decisions do not affect
appearance. Serialized backend recipes take precedence over that fallback.

Four facing drawings change the face, silhouette and front/back accessory layers.
Eight poses comprise a standing pose, six gait phases and a conversational gesture.
Gait uses recorded travel distance; an idle resident does not walk in place. A
wheelchair recipe renders wheels and a seated body. Children retain the same
modular system at 76% adult size. The inspector draws the identical saved recipe.

`CharacterFactory.ts` precomposes each visible recipe once into a shared atlas.
Each 2048 × 2048 page contains up to 80 recipes, with 32 frames per recipe; 300
different residents require four pages. Sprite textures share these pages, and
the owning layer releases them on disposal. Drawing a playback frame never
recomposes a person. Nearest-neighbor scaling preserves the pixels.

At neighborhood zoom, 32 × 48 plates produce readable people around 32–44 screen
pixels tall. Below 0.5 zoom the layer uses small overview markers. The selected
resident remains identifiable. Recorded group members whose large display
sprites would overlap receive stable horizontal display offsets capped at 18
world pixels. Unrelated people are not offset. Selection and camera following
use those displayed feet; recorded locations, route geometry and model outcomes
remain unchanged.

`VehicleLayer.ts` contains the original four-facing, eight-color car plates. Cars
are created only from actual recorded vehicle IDs. Occupancy is derived from
recorded activity transitions: pedestrians remain visible while boarding and
alighting, and disappear while driving/riding. Vehicle selection returns actual
occupant IDs. Both vehicle and pedestrian movement follow the recorded polyline
with its timing; seeking skips interpolation from unrelated frames.

Visual verification artifacts are in `output/playwright/`:

- `campus-characters-contact-sheet.png`: 24 recipes and all four facings/poses.
- `campus-vehicle-contact-sheet.png`: car colors and four facings.

Browser verification found 300 distinct saved recipes for 300 generated IDs and
checked family display selection, boarding/riding/alighting visibility, vehicle
occupant selection, camera positions and non-adjacent seeking. The actual local
40-resident daily recording was then replayed across all 69 frames with vehicle
transitions, at six fractions per frame (414 checks). Every resident was accounted
for exactly once as an indoor occupant, pedestrian or vehicle occupant; there
were no duplicated or missing people. All 361 recorded pedestrian motion paths
in those frames were accepted, including continuous non-cardinal segments.
