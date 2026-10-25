# Columbus winter-storm data feasibility sample

Retrieved **24 October 2026, America/New_York** (25 October UTC). Research artifacts only; not loaded into the simulator.

The bounded fetch successfully retrieved **141 original report rows** for **22–24 December 2022**, spanning `2022-12-22T00:00:00` through `2022-12-24T23:51:00`. The original response is **122,909 bytes**. No cloud inference, AWS resources, API keys, or paid data service were used.

## Station identity was verified before the request

[NOAA's ISD station history](https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv) identifies KCMH / Port Columbus International Airport with USAF **724280**, WBAN **14821**, coordinates **39.991, −82.877**, elevation **246.8 m**, and a listed record interval containing the 2022 sample. Its combined ISD identifier is therefore **72428014821**. The WBAN matches the previously identified normals station **USW00014821**. A second historical KCMH entry with USAF `999999` ends in 1972 and was excluded for this sample. The metadata snapshot currently ends the selected record in 2025; it does not establish current station-feed availability in 2026.

The [ISD format specification](https://www.ncei.noaa.gov/pub/data/noaa/isd-format-document.pdf) documents the USAF/WBAN identifier fields and UTC observation times. These files preserve `DATE` exactly as returned, without conversion to Columbus local time. A simulation importer should explicitly convert UTC to `America/New_York` for the displayed clock.

## Files

| File | Purpose |
|---|---|
| `kcmh-isd-station-metadata.json` | Matching original metadata rows, retrieval time, upstream URL, source size and SHA256 |
| `kcmh-2022-12-22_24-global-hourly-response.csv` | Exact downloaded CSV response bytes |
| `kcmh-2022-12-22_24-global-hourly.csv` | Positional row-filtered CSV; all original columns and field values retained |
| `manifest.json` | Exact API URL/parameters, station evidence, row/date counts, hashes, verification, and quality caveats |

The query used the public [NCEI Access Data Service](https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation), dataset `global-hourly`, the verified station, and a three-day window. The response contains 42 rows for December 22, 55 for December 23, and 44 for December 24. These are **report counts**, not a count of independent evenly spaced hourly measurements.

## Quality and parsing limits

- The response contains **repeated metadata header names**, including `NAME`, `LATITUDE`, `LONGITUDE`, `ELEVATION`, `SOURCE`, `REPORT_TYPE`, `CALL_SIGN`, and `QUALITY_CONTROL`. Preserve positional columns or explicitly rename duplicates. A dictionary-only CSV parser can silently overwrite columns.
- Report types are mixed: **72 FM-15, 54 FM-16, 12 FM-12, and 3 SOD** records. No report-type selection, harmonization, deduplication, resampling, or gap filling has been performed.
- Fields such as wind, visibility, and temperature preserve their original compound encoding, quality flags, scaling, and missing-value sentinels. They are **not immediately interchangeable with displayed mph, miles, or °F**. Decode against the official format and choose an explicit QC policy before charting or simulation use.
- All 141 rows match the requested station and time interval, and every row has the original header's column count. File SHA256 values were checked after writing.
- An airport observation is not a measurement at the Oval or an individual campus building. Sparse station measurements cannot establish a continuous campus-wide hazard field.
- This fetch **does not prove that blizzard conditions held at OSU**, fit hazard probabilities, estimate damage or injuries, or calibrate resident behavior. It establishes that a small, reproducible primary-source weather fixture can be acquired.

Next: define a documented decoder/QC/report-priority policy; review observed gaps and timestamps; then construct a labeled airport weather curve. Keep any campus interpolation separate and explicitly uncertain.
