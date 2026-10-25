# Third-party software

Last Warning uses these projects as dependencies. Preserve their license/copyright notices when redistributing dependency code or a bundled application. Exact application dependencies are recorded in `uv.lock` and `frontend/package-lock.json`; upstream distributions include their license files.

| Software | License | Use |
|---|---|---|
| [Mesa](https://github.com/mesa/mesa) | Apache-2.0 | Model/Agent framework |
| [NetworkX](https://github.com/networkx/networkx) | BSD-3-Clause | Road routing and social graph |
| [NumPy](https://numpy.org/) | BSD-3-Clause | Numerical artifacts and terrain |
| [FastAPI](https://github.com/fastapi/fastapi) | MIT | Validated HTTP API |
| [Pydantic](https://github.com/pydantic/pydantic) | MIT | Schema validation |
| [Uvicorn](https://github.com/Kludex/uvicorn) | BSD-3-Clause | Local ASGI server |
| [Boto3](https://github.com/boto/boto3) | Apache-2.0 | AWS Bedrock runtime client |
| [React](https://github.com/facebook/react) | MIT | Application UI |
| [Pixelify Sans](https://github.com/google/fonts/tree/main/ofl/pixelifysans) | SIL Open Font License 1.1 | Locally bundled pixel display font; full license at `frontend/public/assets/fonts/PixelifySans-OFL.txt` |
| [PixiJS](https://github.com/pixijs/pixijs) | MIT | GPU rendering for the pixel city, residents, hazards and paired replay |
| [Vite](https://github.com/vitejs/vite) | MIT | Frontend development/build |
| [Recharts](https://github.com/recharts/recharts) | MIT | Recorded outcome and neural charts |
| [Lucide](https://github.com/lucide-icons/lucide) | ISC, with MIT Feather-derived portions | UI icons |
| [Meta TRIBE v2](https://github.com/facebookresearch/tribev2), [full checkpoint](https://huggingface.co/facebook/tribev2) and [Mini checkpoint](https://huggingface.co/facebook/tribev2-mini) | CC-BY-NC-4.0 | Separate official inference; downloaded source/weights stay in ignored local caches |

TRIBE attribution: Stéphane d'Ascoli, Jérémy Rapin, Yohann Benchetrit, Teon Brooks, Katelyn Begany, Joséphine Raugel, Hubert Banville, and Jean-Rémi King. *A foundation model of vision, audition, and language for in-silico neuroscience*. arXiv:2605.04326 (2026). Copyright Meta Platforms, Inc. and affiliates. Base feature extractors have their own licenses/terms, including gated Llama access.

The pixel atlas is original project artwork generated from editable local sources under `frontend/art/last-warning/`. No WorldBox sprites, branding, interface artwork or audio are incorporated.

Flood-ABM (MIT), MesaEvac (no top-level license found in the inspected commit), Pixi React (MIT), and MiroFish (AGPL-3.0) were evaluated but their source is not incorporated. See `docs/open-source-reuse.md` for decisions and precise inspected commits. Three.js was used by the previous city renderer and has been removed from the pixel release.

## Campus geography

The campus edition includes a pinned extract of OpenStreetMap data, © OpenStreetMap contributors, available under the Open Database License (ODbL) 1.0. See [copyright and attribution](https://www.openstreetmap.org/copyright), and the source, query, hash and license notice in `backend/app/data/`. The pixel artwork and synthetic household overlays are original authored presentation; they do not reproduce OSU or commercial map tiles.

## Opening globe

The original pixel Earth renderer uses [Natural Earth 1:110m land polygons](https://www.naturalearthdata.com/downloads/110m-physical-vectors/110m-land/), released to the public domain under [Natural Earth's terms of use](https://www.naturalearthdata.com/about/terms-of-use/). The pinned GeoJSON and source/hash manifest are bundled in `frontend/public/assets/geography/`. It is an artistic geographic transition, not a satellite image or live observation.

The continuous geographic descent adds public-domain Natural Earth 1:50m state, lake and river geometry and a simplified Columbus arterial-road/river extract, © OpenStreetMap contributors, under ODbL 1.0. The combined derived geographic asset is `opening-region.geojson`; its adjacent provenance manifest retains source hashes, the Overpass query, source dates and simplification rules. Linked OpenStreetMap attribution remains visible during the opening. These contextual layers are not simulation routes.

`opening-local.geojson` contains simplified OpenStreetMap building, green-space and water footprints around the playable campus, also under ODbL 1.0, with its own adjacent source/query/hash manifest. These footprints provide opening-only context; roof colors and heights are original illustrative styling.
