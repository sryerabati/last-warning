# Campus evidence refresh

Reviewed October 25, 2026. This pass adds a compact, dated evidence catalog for the UI rather than another undifferentiated list of links. It does not silently convert institutional headcounts, transport schedules or airport weather averages into observed behavior on this map.

The UI-ready source is `frontend/src/data/campusEvidence.ts`. Every item includes its period, geographic/population scope, application, limitation and exact primary-source links. `Context only` means the fact is available for explanation and future model work, not an active runtime parameter. The storm category definition is already used in `campus_hazards.py`.

## Verified data and current use

| Topic | Evidence | Use and boundary |
| --- | --- | --- |
| Population | OSU's September 21, 2026 release reports **62,010 Columbus-campus students**, including **47,308 undergraduates**. [Official release](https://news.osu.edu/ohio-state-increases-total-enrollment-to-68183-students/) | Context for student roles. These enrollment counts are not attendance, outdoor occupancy, neighborhood household counts or a scaling factor for the 300 simulated people. No appearance or emergency-response probabilities follow from them. |
| Calendar | The registrar's March 3, 2026 calendar revision gives **August 25–December 9** as the autumn teaching span and **October 15–16** as a class break with offices open. [Registrar calendar](https://registrar.osu.edu/academic-calendar/academic-calendar-5-year-view-2023-2028/) | A future day-type control can distinguish teaching, break and exam days. The current loop is an authored teaching day; it does not inherit the real current date. Dates are subject to revision. |
| Transit | The **2026–27** regular weekday schedule lists Buckeye Express at **7-minute intervals, 07:00–18:00**. East Residential is **15 minutes, 07:00–22:00**, then **30 minutes until midnight**. [CABS schedule](https://ttm.osu.edu/cabs) | A starting point for stop/boarding/capacity work. Scheduled headway is not actual waiting time. CABS is not implemented in the present simulation, and break/holiday/football service differs. |
| Seasonal context | NWS's **1991–2020 Columbus normals** give January mean daily high/low **37.19°F / 21.97°F**, July **85.48°F / 65.52°F**, and January mean monthly snowfall **9.5 inches**. [Normals overview](https://www.weather.gov/iln/climate_normals_cmh), [January table](https://www.weather.gov/media/iln/climo_webpage/CMH_Jan.pdf), [July table](https://www.weather.gov/media/iln/climo_webpage/CMH_Jul.pdf) | Reference for seasonal presentation and ambient scenario presets. Airport long-period averages are not campus measurements, individual-event severity or a forecast. They do not yield disaster frequency. |
| Warning definitions | NWS base severe-thunderstorm criteria are **58 mph wind or 1-inch hail**; destructive criteria are **80 mph or 2.75-inch hail**. [NWS categories](https://www.weather.gov/lot/SevereThunderstormWarningsUpdate) | Already informs scenario terminology and explicit wind/hail fields. It does not validate damage, casualties, uniform intensity or agent compliance. |

## Highest-value next modeling work

1. **Calendar-aware activity presets.** Introduce an explicit authored day type—teaching day, break, exam day—using the published calendar as provenance. Do not download individual student schedules or silently make every worker follow the class calendar. Office/service commitments need separate calendars.
2. **Actual transit before bus decoration.** Pin an ordered CABS route/stop fixture and schedule version; then model waits, seats, boarding and off-map endpoints. Do not add moving bus sprites before those state transitions exist. The schedule alone cannot calibrate passenger demand or travel time.
3. **Seasonal appearance separated from hazards.** Seasonal clothing and ambient vegetation can use a selected season. Severe blizzard/hail/storm presets remain explicit experiments, not randomly sampled from monthly normals.
4. **Aggregate calibration with uncertainty.** Neighborhood ACS vehicle/household estimates require matching tract or block-group boundaries, denominator and margin of error. The prior geography research identifies tables B11016/B08201/B08301; no new ACS counts were imported because a defensible geography crosswalk has not been established. Journey-to-work data is not student travel-to-class data.

These are bounded proposals, not claims that the current simulation has been calibrated. The city footprint, protective-building assumptions, synthetic names and identities, daily timetable and LLM decisions need distinct provenance categories.

## Information architecture

Keep the canvas focused on operating the world. In a **Model & data** drawer, separate:

- **Geography:** source date, extent, real footprint/path geometry and illustrative elevations.
- **People & routines:** synthetic population, household/role rules, day type, names/appearance generation and what the enrollment reference does not measure.
- **Travel:** walking/driving implementation and the currently reference-only transit schedule.
- **Hazards:** definition thresholds, scenario parameters and the distinction between exposure time and injury risk.
- **Models & recordings:** real Bedrock intentions, deterministic physical integration, genuine Mini neural artifacts and provenance hashes.

Within each section, show the short fact first, followed by expandable period/scope/use/limits/source details. A source link should sit with the claim it supports. “Real data” must not be a single badge applied to the entire simulation.

## Pixel Earth opening asset

Natural Earth's **1:110m land polygons** provide an appropriate light geographic base for the requested spinning Earth. Its [terms of use](https://www.naturalearthdata.com/about/terms-of-use/) state that the vector and raster datasets are public domain and can be modified and redistributed. The [dataset page](https://www.naturalearthdata.com/downloads/110m-physical-vectors/110m-land/) links the maintainer's repository.

Pinned locally:

- `frontend/public/assets/geography/natural-earth-land-110m.geojson`
- `frontend/public/assets/geography/natural-earth-land-110m.provenance.json`

The unmodified GeoJSON contains 127 Polygon features and is 138,160 bytes. Download URL: `https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson`. SHA-256: `9e0729ee253ca7d7a5c4ae9395fb1902264c5377c52e224d13dd85010e2835d9`. Longitude/latitude coordinates are for the decorative introductory globe; the campus still uses its separate pinned OSM dataset. No external fetch is required at runtime. The source URL can change upstream, so the committed content/hash is the reproducible snapshot.

## Validation

All five catalog entries were checked against primary pages or linked primary PDFs. Source dates and scope are retained. The globe parses as a FeatureCollection, its Polygon geometry is checked, and its SHA-256 matches the provenance sidecar. No credential access, model inference, cloud resource creation or simulation-parameter changes were needed.
