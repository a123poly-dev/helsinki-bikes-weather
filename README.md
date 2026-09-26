# helsinki-bikes-weather
How does weather influence the number of city bike rides in Helsinki?

## Data sources
- City bike trips: HSL open data (Helsinki Region Transport). All journeys
  in Helsinki and Espoo: origin and destination station, start and end time,
  distance (m) and duration (s). Period: June 2025.
- Station list: HSL city bike stations (Helsinki and Espoo), CSV updated
  23.04.2021. Source: https://public-transport-hslhrt.opendata.arcgis.com/
  Coordinates: `x`/`y` are WGS84 (lon/lat, used); `x2`/`y2` are ETRS-GK25 (not used).
- Weather: Finnish Meteorological Institute (FMI) open data,
  station Helsinki Kaisaniemi, daily observations.

## Project structure
- `pipeline.py` — extract, clean, validate and load data into SQLite
- `queries.sql` — analysis queries (Q0–Q5)
- `explore.py` — data exploration and quality checks
- `reference/stations_manual.csv` — manual fixes for stations missing in the 2021 list

Tools: Python, pandas, SQLite.

## How to run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python pipeline.py
sqlite3 data/bikes.db < queries.sql
```
Output: `data/bikes.db` with tables `trips`, `stations`, `weather`.

## Data exploration

### Trips (HSL city bikes, June 2025)
- 387,257 trips, 8 columns, no missing values
- Departure/Return stored as text → converted to datetime
- Outliers: negative distances (min −4,294 km, likely an overflow bug),
  distances up to 3,680 km, trips of 0 seconds and up to 114 days
- Typical trip: ~11.5 min, ~2.1 km (median)
- 2 trips had Departure without time. No trips had exactly 00:00:00 with time,
  while nearby seconds had ~1.75 trips/sec. Conclusion: the export drops
  the time when it is exactly midnight.
- Duration is on average ~4 sec shorter than Return − Departure.
- 3.3% of raw trips differ by more than 10 sec (up to 25 days).
  After cleaning, 5,343 trips (1.4%) differ by more than 60 sec →
  flagged, not removed (`duration_mismatch`).
- Station IDs are text codes, not numbers: most have leading zeros ("044"),
  one station uses "*40" (Puotila, 1,378 trips). IDs are stored as text
  and converted to numbers only to match the reference list.

### Weather (FMI, Helsinki Kaisaniemi, June 2025)
- 30 daily rows, no missing values, no gaps in dates
- Date is split into Year / Month / Day → combined into one `date` column
- Precipitation uses FMI code −1 for "no precipitation" → converted to 0
- Rainy day = precipitation ≥ 1 mm (14 of 30 days)
- Weather is taken from one station in central Helsinki (Kaisaniemi).
  11.2% of trips start in Espoo; local weather differences are ignored.

### Station reference (HSL station list)
- The station list is from April 2021, trips are from June 2025.
- In the reference list, an empty city field means Helsinki (347 stations);
  Espoo has 110 stations.
- Station IDs match between trips and the reference for 443 of 456 stations.
  7 IDs point to different stations (IDs were reused after renaming),
  6 stations are missing from the reference. Their city was filled manually
  from the HSL app (`reference/stations_manual.csv`).
- Join rule: by ID, accepted only if the names also match
  (ignoring whitespace and truncated names in the reference).
- One station name ("Vallilan varikko") contains a non-breaking space (\xa0)
  in the trip data (942 departures, 677 returns). Names are normalized
  in the pipeline.
- City share of trips: Helsinki 88.8%, Espoo 11.2%.

## Cleaning rules

Removed 2.7% of trips (June 2025):
- invalid date: date could not be parsed (safety net for unknown formats; 0 in June)
- distance ≤ 0 m or > 50 km (sensor errors)
- duration < 60 sec (false starts: bike taken and returned immediately)
- duration > 5 h (likely not returned in time)
- return to "Workshop Helsinki" (ID 997, 24 trips): the bike was not returned
  to a station; the return time and place are when HSL collected it
  (durations from ~22 hours to 24 days)

Rules overlap: most zero-distance trips are also shorter than 60 sec —
consistent with "false starts".

## Fixes and flags

Rows below are kept, not removed:
- `departure_fixed`: Departure without time (2 trips), set to 00:00:00.
- `duration_mismatch`: Duration differs from Return − Departure by more
  than 60 sec (5,343 trips).
- `over_limit`: trip longer than 1 hour.

## Results (June 2025)

### Average trips per day, rainy (≥ 1 mm) vs dry

| Day type | Dry    | Rainy  | Effect | Days (dry / rainy) |
|----------|--------|--------|--------|--------------------|
| Weekday  | 15,806 | 10,796 | −32%   | 9 / 11             |
| Weekend  | 14,333 | 10,521 | −27%   | 5 / 2              |

- Rain reduces bike trips by about one third.
- Midsummer (20–22 June) is excluded: even dry days had ~40% fewer trips.
- Limitation: one month, few rainy weekends — results are indicative.

### Weekdays by rain intensity

| Rain            | Days | Trips/day | Effect |
|-----------------|------|-----------|--------|
| Dry (< 1 mm)    | 9    | 15,806    | —      |
| Light (1–5 mm)  | 6    | 12,397    | −22%   |
| Heavy (> 5 mm)  | 5    | 8,874     | −44%   |

- The effect grows with rain intensity: heavy rain cuts trips twice as much
  as light rain.
- Exception: Mon 16 June (3.2 mm) had a normal number of trips — rain timing
  matters (e.g. night rain). Hourly weather data would be needed to check this.

### Trips per hour (average per day, Midsummer excluded)

- Weekdays: two commute peaks — 8:00 (~930 trips) and 16–17 (~1,320).
  The evening peak is 1.4× higher than the morning one.
- Weekends: a wide plateau from 14 to 18 (~1,050–1,120 trips per hour).
- Nights after Friday and Saturday: 3–5× more trips at 00–03 than on weekdays.
- After 18:00 weekdays and weekends look almost the same.
- Commute peaks match Finnish working hours, which confirms timestamps
  are in local time.

### Stations

- Top 10 stations (all in Helsinki) account for ~12% of trips — demand is
  spread across hundreds of stations.
- Many top stations are rail or metro hubs (Pasila, Rautatientori, Kalasatama,
  Sörnäinen), which suggests first/last-mile use.
- Busiest stations: Helsinki — Itämerentori (6,744 trips); Espoo — Aalto
  University metro station (2,983), followed by Otaniemi and Leppävaara.

### 7-day moving average

- Two dips in June: after heavy rain (11–13 June, ~12,100 trips/day) and
  during Midsummer with rain (23–25 June, ~9,000).
- By the end of June the average did not return to the early-June level
  (~12,500 vs ~14,000): rain on 27–29 June or the start of summer holidays.
  One month of data is not enough to separate these effects.