# Last Warning original art · revision 3

All 245 sprites and tiles were authored specifically for Last Warning. No external asset packs, copied game sprites, paid assets, or generated model images are included. `generate_atlas.py` is the editable source; it draws at integer coordinates without antialiasing. Runtime atlas, palette and frame metadata are emitted to `frontend/public/assets/art/last-warning/town-atlas.{png,json}` so the existing production `/assets` mount serves them. Revision 3 adds stepped oak crown variants and refines foliage silhouettes and contact shadows. Resident palettes and fixed sprite foot anchors stay unchanged.

Terrain tiles are 16×16 pixels. The city maps four art tiles to each logic-cell edge (64 source pixels per logic unit). Buildings and props use fixed foot anchors in the renderer. Resident appearances are stable per ID and recorded art seed; direction and gait do not change their appearance. Art is presentation only and adds no simulation mechanics.

Regenerate with Python 3 and Pillow: `python generate_atlas.py`. The runtime needs only the PNG and JSON.
