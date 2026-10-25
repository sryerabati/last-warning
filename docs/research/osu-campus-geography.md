# Ohio State campus geography, population, and movement evidence

Research date: 2026-10-24. Research only; no application code, map import, or paid service was changed. Sources below are public primary sources. Recommendations are design proposals unless identified as observed facts.

## Recommended playable place

Build a geographically recognizable **Columbus campus core plus a small University District edge**, rather than trying to recreate all of Columbus at once. Proposed bounds are Lane Avenue on the north, 11th Avenue on the south, the Olentangy river corridor on the west, and Indianola Avenue on the east. Include a narrow west-bank buffer where a road crosses the river. These are proposed game bounds, not an official neighborhood boundary. Calculate the actual area after loading geometry; do not invent a square-kilometre figure.

The first camera should frame the Oval, Thompson Library, and Mirror Lake at a scale where individual people are legible. A second overview can show Ohio Stadium and the river. The campus’s recognizable identity comes from lawns, crossing footpaths, institutional buildings, residence complexes, and the High Street edge. Rows of detached cottages would misrepresent its center.

Use exterior footprints and public circulation only. Building interiors, security systems, actual room occupancy, and response-team locations are outside this recreation.

### Geographic anchors verified against the official tour map

The official [OSU self-guided tour, map on PDF page 2](https://campusvisit.osu.edu/media/kpwoxu0v/self-guided.pdf) was downloaded and visually inspected during this research. The map has no clear publication date in the material inspected; pin its download date and hash if retained as a reference. Its topology supports these anchors:

| Anchor | Relationship to preserve | Visual treatment proposed |
|---|---|---|
| The Oval | Between Thompson Library on the west and College Road on the east | Large open lawn crossed by diagonal paths; gathering groups at path junctions |
| Mirror Lake | South of the Oval, near Pomerene Hall | Irregular water, planted banks, benches, quieter foot traffic |
| Ohio Union | East/southeast of the Oval, along High Street | Large social destination with arrival and departure activity |
| Ohio Stadium | Northwest of the Oval and east of the Olentangy | Recognizable horseshoe silhouette; ordinary-day perimeter activity |
| RPAC | South of the stadium and west of Thompson | Recreation destination, sports bags, evening arrivals |
| North and south residence areas | North around Woodruff/Lane; south around 12th/11th | Larger shared residences, roommate departures, dining trips |
| River and road crossings | River west of the main academic core; Woody Hayes and Herrick crossings | Continuous water barrier, valid bridge connections, distinct bank paths |

The [official campus-map guide](https://fits.osu.edu/kb/how-guide-campus-map) confirms building/named-place lookup, walking routes with distance/time, transit stops, and parking layers. Use it to verify public wayfinding. Access to the site does not establish permission to redistribute its artwork or underlying data. Do not trace Google Maps or copy OSU map tiles into the game.

## Source-to-feature and acquisition plan

All undated live pages in this table were reviewed on 2026-10-24. A data manifest should preserve source URL, retrieved date, source revision, license, feature IDs, bounding box, file hash, projection, and transformations. Keep the geographic source bundle separate from game sprites and behavioral configuration.

| Source and version | Available public material | Proposed use | Rights, update, and reliability limits |
|---|---|---|---|
| [OpenStreetMap copyright/license](https://www.openstreetmap.org/copyright) | Vector roads, paths, water, buildings, land use; a bounded extract can retain original IDs/tags | Primary candidate for reproducible geometry, transformed into a local metric coordinate system | ODbL; attribute contributors and preserve the applicable database obligations. Completeness and access tags require checking. An open database is not a guarantee of a free production API. |
| [OSMF attribution guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines), adopted 2021-06-25, page edited 2026-09-10 | Specific guidance for computer games and simulations | Readable credit in the game menu/credits, with linked license and detailed provenance | Game guidance permits several suitable locations. Keep attribution accessible while preserving a clean main scene. |
| [OSMF tile policy](https://operations.osmfoundation.org/policies/tiles/) | Policy for the standard public raster tile service | Do not make this a runtime dependency; render original pixel art over extracted geometry | Bulk downloading and offline tile archives from `tile.openstreetmap.org` are prohibited. Obtain vector data through an appropriate bounded extract service instead. |
| [City of Columbus public Buildings layer](https://maps2.columbus.gov/arcgis/rest/services/Applications/CSIR_Public/MapServer/5) | Polygon layer; JSON, GeoJSON, PBF; pagination; 2,000-record limit; name, story-count, height, and update fields; source projection 3857 | Optional footprint comparison and massing reference | Copyright field is blank, which is not a reuse grant. Confirm item license/provenance before distribution. Missing heights remain unknown. Do not collect editor identities or unrelated records. |
| [OSU CABS page](https://ttm.osu.edu/cabs), 2026–27 schedule | Routes, headways, calendars, public stop lists | Campus buses as actual vehicles with stop queues and passenger boarding | CABS is free campus transit; schedules vary during breaks, holidays, and football Saturdays. No public CABS GTFS feed was verified in this research. |
| [CABS system map PDF](https://ttm.osu.edu/sites/default/files/documents/cabs-system-map.pdf), current document dated 7/31/26 | Public route geometry and ordered stops | Independently verify the campus network and selected shuttle routes | A search index initially showed an older 2025–26 version at this same URL. Following the live page returned the 2026–27 document. Save a hash; the URL is not a version identifier. |
| [COTA data](https://www.cota.com/data/) | Static GTFS; real-time alerts, trips, and vehicle positions; GIS/KML links | Optional regional bus routes entering/exiting the map, using a pinned GTFS timetable | Terms grant limited, revocable data-use rights and reserve changes/withdrawal; they restrict associated trademarks/copyrighted material. Use original bus art, avoid endorsement claims, and retain terms. COTA and CABS are separate services. |
| [MORPC traffic counts](https://www.morpc.org/tool-resource/traffic-counts/) | Multiagency public count database, searchable by location/criteria | Candidate validation data for corridor-level vehicle arrivals | No campus-specific counts were downloaded or calibrated here. Record count station, date, duration, and measure before use. Daily traffic volume is not simultaneous occupancy. Check dataset-specific reuse conditions. |
| [Census ACS 5-year API documentation](https://www.census.gov/data/developers/data-sets/acs-5year.html), 2020–24 release documented January 29, 2026 | JSON API and detailed estimates down to block groups | Aggregate constraints on surrounding households, vehicle availability, and resident commuting | These are period estimates, not real-time observation. Keep estimate, margin of error, and annotation variables. Do not assign an estimate to a specific real household. |
| [OSU enrollment release](https://lima.osu.edu/story/feature-enrollment-2026-09-28), September 28, 2026 | Current institutional student headcounts | Ground the campus’s student-heavy identity and distinguish undergraduate/graduate roles | Columbus: 62,010 total students; 47,308 undergraduates; 8,585 new first-year students. These are not the people present in this bounded map at a given hour. |

The City’s indexed University District community-profile PDF appeared to contain Esri forecasts, but its direct URL returned 404 during verification. Do not import those figures as Census measurements. A future data acquisition pass can resolve the current official file and its footprint/forecast methodology.

## People who fit the place

The population must be synthetic. Use generated identities and relationships, never university directories, actual timetables, identifiable commuters, or real residential occupants. Role, destination, clothing, mobility, and schedule are separate properties; avoid mapping demographic appearance to danger response or competence.

Recommended household and social units are: residence-hall roommates, off-campus shared apartments/houses, single adults, partners, families with dependents, and people who commute from outside the map. A family need not live on campus to appear there; a weekend visit or a community walk supplies a plausible context. Professors, other employees, service workers, graduate students, undergraduates, and local residents need distinct kinds of destinations without rigidly deterministic personalities.

Use [ACS B11016, household type by size](https://api.census.gov/data/2024/acs/acs5/groups/B11016.html) for family/nonfamily household constraints and [B08201, household size by vehicles available](https://api.census.gov/data/2024/acs/acs5/groups/B08201.html) for shared vehicle access. These tables do not measure residence-hall roommate arrangements. Treat group quarters separately instead of turning every dorm room into a Census family household.

[B08301 measures transportation to work](https://api.census.gov/data/2024/acs/acs5/groups/B08301.html); it is not a student journey-to-class table. Use it only for an appropriate resident-worker population. A [2019 OSU study summary](https://news.osu.edu/to-increase-bike-commuters-look-to-neighborhoods/) reports a 1,200-person campus commuter survey and links bicycle commuting with neighborhood density. It supports modeling mode choice in relation to home location; its historical percentages should not be used as a 2026 campus mode share.

Suggested implementation configuration, explicitly an assumption: begin with roughly 500 individually simulated residents/visitors, then profile 250–1,000. This is a playable sample, not a 1:1 campus census and not an inferred count of people outdoors. Keep actual simulated people distinct from any decorative distant crowd. Never multiply fatalities or compliance estimates by a hidden population scale.

Daily life should use activity chains with flexible windows: residence → dining → class → library → café → recreation → home; off-map home → parking → office → lunch → parking → off-map; shared home → bus stop → work → errands → reunion. Add persistent roommate/friend/household relationships, agreed meeting times, delays, and remembered cancelled plans. Class changes can create short waves, while staff shifts and flexible research schedules prevent synchronized mass departures. These schedules are plausible scenario assumptions until validated against appropriate public aggregate observations.

The [Census guidance on margins of error](https://www.census.gov/help/topics/faq.do-i-need-to-consider-the-margins-of-error-when-comparing-acs-estimates.html) requires acknowledging sampling uncertainty. Neighborhood estimates should constrain broad mixtures rather than imply exact resident counts in each building.

## Multimodal movement that is visible and coherent

The following is a proposed engineering design, not a claim about a calibrated campus model:

1. **Walking graph:** Public paths, sidewalks, crossings, public building entrance connectors, and bridge edges. Store metric lengths and relevant access/steps/surface tags. An unknown accessibility attribute stays unknown. Do not label every route wheelchair-accessible simply because it is connected.
2. **Vehicle graph:** Directed road edges with permitted access and turns. Parking is a destination/transfer state, not a car driving over the Oval. An agent walks to a parked vehicle, boards, drives, parks, then walks. The vehicle retains its identity and location.
3. **Transit graph:** Timetable/route edges linked to walkable stop nodes. Agents wait, board a particular bus, ride, and alight. Truncated routes need explicit off-map portals instead of teleporting buses across the river or the lawn.
4. **Groups:** A family or friend group can follow a shared route with modest offsets, a rendezvous, waiting, and occasional separation. Each person has a real position; passengers attach to a vehicle rather than being drawn as simultaneous pedestrians.
5. **Time and motion:** Preserve physical distance and travel duration in simulation seconds. Render fluid movement between simulation snapshots; sprite animation speed must not determine travel speed. A faster playback changes the clock, not the modeled walking speed.
6. **Hazard interaction:** Apply closures/cost changes to relevant edges, keep already-traveling agents on a coherent edge, and replan at defined decision points. Weather protection, limited visibility, and available transport are state inputs. No vehicle or person should cross a water polygon without a valid connection.

The official [CABS network](https://ttm.osu.edu/cabs) already supplies distinct campus movement patterns: Buckeye Express links the academic core via Woody Hayes/Woodruff, High Street and College Road; Campus Connector serves the west-side parking connection; East Residential reaches off-campus streets. For the bounded first scene, choose one verified route fragment and explicit portals before attempting the entire network. Bus headways and capacity used in a scenario should show whether they are source values or simplifying assumptions.

## Implications for this repository

Read-only inspection of `backend/app/simulation/world.py` and `life.py` found a fixed 40×40 fictional world, a shared cardinal graph, seeded households of four, and daily movement over that graph. The organic layout is handcrafted, not georeferenced. The existing code is a useful replay scaffold but does not yet contain a geographically grounded multimodal model.

Add a versioned campus scenario rather than silently redefining the coordinates of old runs. Separate geographic geometry, hazard sampling, route topology, building/activity metadata, and artistic rendering. A hazard raster may still be useful, but road and footpath connectivity should not be reduced to coarse square cells. Store a map version and behavior-configuration hash with each run.

A practical first delivery can contain the six recognizable anchors above, public-path/road geometry, three household types, student/staff/local-resident activity templates, pedestrians plus a few functioning parked cars, and one functioning bus route. More buildings should follow only after people visibly board, meet, wait, enter, and leave correctly.

## Validation and claims gate

- Compare landmark positions and river crossings against the official map; inspect the actual extracted vector geometry before artistic simplification.
- Validate three representative public walking routes against official campus wayfinding distances. Explain differences introduced by a bounded map or simplified entrances.
- Ensure vehicles cannot use walk-only paths; a bridge does not connect to water below it; a disconnected route returns a visible failure state instead of teleporting.
- Verify round trips, parking/boarding conservation, passenger identity, and no people duplicated between street and vehicle.
- Check source licenses, hashes, and source dates before distributing the map bundle. Publicly accessible data with missing license metadata stays an unresolved ingestion candidate.
- Present the result as an educational simulation grounded in public geography and aggregate context. Do not call its casualties, evacuation time, individual decisions, or campus occupancy empirically accurate until separately validated. A recognizable place and believable animation are different achievements from predictive validity.

Open data work remaining: acquire and inspect the actual bounded vector extract; resolve optional City layer reuse rights; verify CABS machine-readable feed availability or author a clearly versioned route fixture; select matching Census geographies and retain uncertainty; inspect any chosen MORPC count stations. None of these data-calibration steps was performed in this research-only pass.
