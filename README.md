# helsinki-bikes-weather
How does weather influence the number of city bike rides in Helsinki?

## Data sources
- City bike trips & stations: HSL open data (Helsinki Region Transport)
(The Origin–Destination (OD) data of city bike stations includes all journeys made by city bikes in Helsinki and Espoo. The data includes information about the origin and destination station, start and end times, distance (in meters) and duration (in seconds) of each journey.)
Data period: June 2025.
- Weather: Finnish Meteorological Institute (FMI) open data,
  station Helsinki Kaisaniemi, daily observations
   
## Data exploration
   ### Trips (HSL city bikes, June 2025)
- 387,257 trips, 8 columns, no missing values
- Departure/Return stored as text → convert to datetime
- Outliers: negative distances (min −4,294 km, likely an overflow bug),
  distances up to 3,680 km, trips of 0 seconds and up to 114 days
- Typical trip: ~11.5 min, ~2.1 km (median)
- 2 trips (June) had Departure without time. Analysis showed no trips
  at exactly 00:00:00 with time, while nearby seconds had ~1.75 trips/sec.
  Conclusion: the export drops time when it is exactly midnight.
  Fixed by setting time to 00:00:00 (flag: `departure_fixed`).
- Duration is on average ~4 sec shorter than Return − Departure.
- 3.3% of trips have a larger mismatch (up to 25 days) → flagged,
  not removed (`duration_mismatch`).

### Weather (FMI, Helsinki Kaisaniemi, June 2025)
- 30 daily rows, no missing values, no gaps in dates
- Date is split into Year / Month / Day → combined into one `date` column
- Precipitation uses FMI code −1 for "no precipitation" → converted to 0
- Rainy day = precipitation ≥ 1 mm (14 of 30 days)
  
### Station reference (HSL station list)
- Empty city field = Helsinki (347 stations), Espoo = 110
- Station IDs match between trips and the reference for 443 of 456 stations.
  7 IDs point to different stations (IDs were reused after renaming),
  6 stations are missing from the reference.
- Join rule: by ID, accepted only if the names also match
  (ignoring whitespace and truncated names in the reference).
- One station name ("Vallilan varikko") contains a non-breaking space (\xa0)
  in the trip data (1,619 trips). Names are normalized in the pipeline.
- City share of trips: Helsinki 87.7%, Espoo 10.6%, unverified 1.6%.

## Cleaning rules

Removed 2.7% of trips (June 2025):
- invalid date: date could not be parsed (safety net for unknown formats; 0 in June)
- distance ≤ 0 m or > 50 km (sensor errors)
- duration < 60 sec (false starts: bike taken and returned immediately)
- duration > 5 h (likely not returned in time)

Rules overlap: most zero-distance trips are also shorter than 60 sec —
consistent with "false starts".

## Fixes and flags

Rows below are kept, not removed:
- `departure_fixed`: Departure without time (2 trips). The export drops at 
  the time when it is exactly midnight, so time is set to 00:00:00.
- `duration_mismatch`: Duration differs from Return − Departure by more
  than 60 sec (5,346 trips).
- `over_limit`: trip longer than 1 hour (free time limit).
