# Continuous opening: geographic context

The Earth → Ohio → Columbus → Oval opening now has locally pinned geographic context at intermediate scales. These shapes support a cinematic introduction; they do not alter the simulator's route graph, hazard geometry or resident model.

## Geographic anchor

The live campus renderer's focus is the Oval at **longitude −83.0123, latitude39.9994**, as defined by `CAMERA_FOCUS` in `backend/app/simulation/campus_world.py`. The previous decorative opening targeted a different campus-adjacent point. Matching this exact anchor avoids drifting sideways at the end of the new move.

The live campus source bounding box is **[−83.0183,39.9940,−83.0003,40.0045]**, ordered west/south/east/north. Its source projection uses a WGS84 local tangent approximation and **24.25meters per world unit**. A cinematic projection must map the live world through this source transform rather than guessing the Oval's screen position.

## Pinned asset

- `frontend/public/assets/geography/opening-region.geojson`
- `frontend/public/assets/geography/opening-region.provenance.json`

The standard GeoJSON FeatureCollection is **277,211bytes**, approximately **63.6KB gzip**, and contains **571features**:

| Layer | Count | Source / extent |
| --- | ---: | --- |
| `state` |16| Ohio and selected surrounding US states/Ontario, complete Natural Earth polygons |
| `lake` |6| Five Great Lakes plus Lake Saint Clair |
| `river` |6| Regional Ohio/Wabash/Allegheny lines and Columbus Scioto/Olentangy lines |
| `road` |543| Bounded Columbus motorway/trunk/primary/secondary/tertiary chains |

Each feature has `properties.layer`, `name` and `source`; local roads/rivers also have `class`. Coordinates are longitude/latitude. Geometry types are Polygon, MultiPolygon, MultiLineString and LineString. The source field distinguishes `natural-earth-50m` from `openstreetmap`. This is a selected visual hierarchy, not a complete local road or water inventory.

## Sources and transformation

[Natural Earth 1:50m administrative boundaries](https://www.naturalearthdata.com/downloads/50m-cultural-vectors/50m-admin-1-states-provinces/), [lakes](https://www.naturalearthdata.com/downloads/50m-physical-vectors/50m-lakes-reservoirs/), and river centerlines were downloaded from the maintainer's `nvkelso/natural-earth-vector` repository. Natural Earth's [terms of use](https://www.naturalearthdata.com/about/terms-of-use/) place its vector/raster datasets in the public domain. The individual URLs and original-response SHA-256 hashes are retained in the provenance sidecar.

Columbus context comes from a bounded OpenStreetMap Overpass query for arterial highways and river centerlines. The query is preserved verbatim in the manifest. Outer extent: **west−83.23/south39.86/east−82.80/north40.15**; lower road classes use smaller nested extents around the campus/downtown core. Returned complete ways can extend slightly outside those selection boxes. No personal data, addresses, contributors or resident information are retained. Only public road/river coordinates, feature names and road classes are used.

Natural Earth polygons were simplified with a0.008° tolerance; regional rivers use0.004°. OSM roads use0.00004° and local rivers0.00008° (degree-space tolerances, not fixed-distance accuracy guarantees). Line fragments with matching name/class were merged only at shared degree-two endpoints. No roads were invented and no gaps were bridged. Six-decimal coordinate rounding is applied. The original campus source files are unchanged.

OpenStreetMap is licensed under [ODbL1.0](https://www.openstreetmap.org/copyright). Keep **© OpenStreetMap contributors** visible and linked while showing its Columbus/campus geography. Retain attribution and the provenance/derived dataset when distributing this asset. Natural Earth and OSM remain separately identified; combining their display does not make OSM public domain.

## Validation

All571 features were checked for finite WGS84 coordinates and appropriate nonempty geometry. Polygon rings remain closed with at least four points; lines have at least two. Required Ohio, Lake Erie, Scioto and Olentangy features are present. Ohio's simplified extent is geographically consistent. File size, feature counts and SHA-256 match the manifest.

Asset SHA-256: `47684b67ffa02141e805ef59442cdaae66431fe611971cffdc051f556640120e`.

The opening should load these local files rather than make runtime Overpass or external map-tile requests. Road/lake widths, terrain color, buildings outside the existing campus and camera motion remain visual interpretation. Neither the regional dataset's coarse scale nor the cinematic presentation establishes navigation accuracy or emergency suitability.

## Surrounding local context

`frontend/public/assets/geography/opening-local.geojson` supplies actual nearby footprints so the detailed live campus is surrounded by a continuous neighborhood, rather than appearing as an isolated rectangular tile. Its separate provenance is in `opening-local.provenance.json`.

One additional bounded OSM request selected closed building, green-space and water ways in **[−83.030,39.986,−82.990,40.014]**. Polygons wholly inside the existing campus selection box were excluded; actual footprints overlapping its edge remain so the renderer can clip context against the live campus. Only complete closed ways are retained. Multipolygon relations were not requested, so some complex parks/buildings may be absent rather than reconstructed incorrectly.

The result contains **4,984 building**, **423 green-space**, and **nine water polygons**, grouped into **36 MultiPolygon features** by layer/class/name. Its raw size is **763,629bytes**, approximately **137.5KB gzip**. All features use `layer: building|green|water`. Building classes are `house|apartments|large`; names are retained only for public green/water features. General building categories and coordinates are visual context, not evidence about occupants. No addresses, owner names or contributor metadata are included.

Small sheds, garages, roofs and structures below approximately65m² were omitted. Greens below350m² and water below100m² were omitted. Footprints were simplified by roughly1–2meters, with the second pass rejected when it changed area by15% or more. Original orientation is preserved. Coordinates are rounded to five decimal places. Whole selected ways can extend slightly beyond the request box. Source colors, roofs, height and shadows remain artistic interpretation.

All retained rings are closed, finite, nonempty and have positive planar area. The asset/hash/count metadata matches its sidecar. SHA-256: `3ebc8f91b0fccfc7e0c1d2c3774a2db52c44b766cddbe927eab4b36692bab40f`.

This opening-only context remains **© OpenStreetMap contributors / ODbL1.0**. It does not add buildings, destinations, residents, routing or shelter claims to the live simulator.

## Surrounding streets, paths and trees

`frontend/public/assets/geography/opening-local-network.geojson` adds the smaller streets, pedestrian paths and mapped trees that connect those surrounding footprints. Its provenance is pinned in `opening-local-network.provenance.json`; the original query, response hash, source date and transformations are preserved there. The source was fetched through the [Private.coffee Overpass instance](https://overpass.private.coffee/api/interpreter), listed in the [OSM public instance directory](https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances). Its returned OSM base date is **2026-07-28**, retrieved on 2026-10-25; this is a dated visual snapshot, not a live map.

The query uses the same **[−83.030,39.986,−82.990,40.014]** outer box as the local footprint asset and selects only `highway=residential|service|footway|path|pedestrian|cycleway` ways and `natural=tree` nodes. It produces **7,509 features**: **2,252 road lines**, **2,414 path lines**, and **2,843 actual mapped tree points**. The asset is **1,648,807 bytes**, approximately **139.5 KB gzip**. Its SHA-256 is `71a49df4ca7d12d5074427d6d81ae5970ce70e19fb9c5867fbe96a218a0cd092`.

Every feature has a stable source-derived `id`, a `layer` (`road`, `path`, or `tree`), a general `class`, and `source: openstreetmap`. Geometry is exclusively LineString or Point in longitude/latitude. No tree positions are synthesized. The source includes 237 residential and 2,015 service line pieces; paths include 2,374 footway, 29 cycleway, seven path and four pedestrian pieces. Service lines may represent public or private access lanes; rendering them does not grant route access.

Lines are simplified with a 0.000004° Douglas–Peucker tolerance, then clipped to the outer box and split around **[−83.0183,39.9940,−83.0003,40.0045]**, the existing campus survey rectangle. Trees inside that rectangle are excluded. This prevents duplicate campus paths/trees while preserving real edge connections. Highway ways tagged `area=yes` are omitted rather than mistaken for centerlines. Six-decimal coordinate rounding is applied. Finite coordinates, unique IDs, nonempty lines, bounds and the excluded campus interior are validated by `scripts/prepare-opening-local-network.py`. Its source/query arguments permit reproducing the pinned transformation without any runtime network request.

Only public geometry, general road classes and source IDs are retained; names, addresses, contributor details and unrelated tags are omitted. Keep the same visible **[© OpenStreetMap contributors](https://www.openstreetmap.org/copyright)** attribution and ODbL terms as the other local context. The network is opening scenery only and makes no claim about current access, emergency shelter, physical tree condition or simulator routing.
