# Open-source reuse audit

Investigated on 2026-10-24 before major application code. Clones live outside the application in `/tmp/last-warning-research`. Third-party repository instructions were treated as project content. No third-party application source was copied into the simulator.

| Candidate | Evaluation / execution | Decision |
|---|---|---|
| [Mesa](https://github.com/mesa/mesa), main `e3d9d5e51216ad46c522f0895f8d56de98d88fab` | Inspected agent/model lifecycle and example. Installed **3.3.1**, ran its upstream BoltzmannWealth example with 100 agents for five steps successfully. Current main differs from stable APIs. | Use pinned stable Mesa for actual Model/Agent lifecycle. Apache-2.0. |
| [Flood-ABM](https://github.com/uofs-simlab/flood_abm), `41cb39e30d76e9986b1b1e7d977910efcae8975a` | Clone initially failed checkout because git-lfs was unavailable; recovered source with LFS processing disabled. Read decision, GIS, and flood-space code. Attempted upstream server; import stopped at missing mesa_geo. Its flood layer uses supplied Calgary polygons and sampled heights, with Mesa 2.1.2 / Mesa-Geo 0.7.1. | MIT; not copied. GIS assets, LFS data, old Mesa lifecycle, and static flood layers cost more to adapt than a documented fictional-cell model. Full GIS environment was not installed or claimed runnable. |
| [MesaEvac](https://github.com/MJones235/mesa-evac), `78e9ea5da07a4cb4e02d413436d4c1d80fa30420` | Inspected evacuation model, OSM/GeoPandas/igraph road network, and requirements. Import smoke test stopped at missing mesa_geo. Pins Mesa 2.1 and substantial GIS stack. No top-level license found in inspected clone. | Not copied or installed. Fixed fictional town needs neither OSM data downloads nor an older GIS stack. |
| [NetworkX](https://github.com/networkx/networkx) **3.5** | Actual Watts–Strogatz generation, subgraph views and multi-source Dijkstra run in every verified simulation. Movement and closed-road routing covered by tests. | Use directly; BSD-3-Clause. No custom replacement graph algorithms. |
| [PixiJS](https://github.com/pixijs/pixijs), [Pixi React](https://github.com/pixijs/pixi-react) | Reviewed current React rendering architecture and WebGL setup. No GPU rendering benchmark or Pixi example executed. | Not integrated: Canvas 2D draws 300–1000 small residents and a 1600-cell town without lifecycle/WebGL overhead. Canvas rendering verified in Chromium. Both Pixi projects are MIT. |
| [Meta TRIBE v2](https://github.com/facebookresearch/tribev2), `af58661791a351a448a489042a28f6c37e1c14b7`; [weights](https://huggingface.co/facebook/tribev2) | Inspected official `TribeModel.from_pretrained`, `get_events_dataframe`, `predict`, notebook, and dependencies. Downloaded neuralset 0.0.2 source without dependencies to verify `Segment.start`. Resolved the full official Linux/Python 3.12 dependency set. Worker dry-run and NPZ serialization/import tested; real weights/GPU inference not run. | Separate official inference integration. CC-BY-NC-4.0; preserve attribution and noncommercial restrictions. Actual model revision resolved immutably at job execution. |
| [MiroFish](https://github.com/666ghj/MiroFish) | Read project overview and license/cost implications. No code run or imported. | AGPL-3.0, LLM/service-heavy architecture; unnecessary for deterministic social diffusion. |

Additional GitHub searches for Mesa evacuation, warning propagation, and flood models did not reveal a smaller compatible foundation worth adding. Mature libraries are used for framework lifecycle, pathfinding, social graph generation, arrays, validation, API serving, charts, and browser QA. The original project code supplies fictional geometry, behavioral assumptions, cellular flood rules, keyed common random numbers, persistence, comparisons, UI, and the integration adapter.

## Skills and tools

- Read and applied `frontend-skill` for a restrained workspace organized around the simulation.
- Read and applied `Playwright` for actual Chromium browser interaction and playback checks.
- Inspected Sites capability; its Workers-hosted architecture does not host this requested local Python/Mesa/SQLite backend. No Site created or deployed.
- Inspected available app tools and user/repository instructions, honored the Buffer context instruction, and installed the missing RTK CLI to follow the user's command-prefix convention. No unrelated Buffer account action was taken.
- No unnecessary skills or simulation frameworks installed. No subagents used.

App dependency versions are reproducible through `uv.lock` and `frontend/package-lock.json`; GPU dependency resolution is in `backend/requirements-tribe.lock`. The GPU lock is resolution-tested, not installation/inference-tested. License notices are in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
