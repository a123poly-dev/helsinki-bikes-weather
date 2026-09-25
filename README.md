# helsinki-bikes-weather
How does weather influence the number of city bike rides in Helsinki?

 ## Type of data:
   
1.1. The Origin–Destination (OD) data of city bike stations includes all journeys made by city bikes in Helsinki and Espoo. The data includes        information about the origin and destination station, start and end times, distance (in meters) and duration (in seconds) of each journey.
Data period: June 2025.
   
## Data exploration (June 2025)
   
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
