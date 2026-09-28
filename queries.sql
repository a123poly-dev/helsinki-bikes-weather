-- Analysis queries. Run: sqlite3 data/bikes.db < queries.sql
-- Views `daily_trips` and `hourly_trips` are created by pipeline.py.
-- Rain thresholds and holidays are defined in one place:
-- pipeline.py (RAIN_THRESHOLD_MM, HEAVY_RAIN_MM) and reference/holidays.csv.


-- Q0. Trips per day with weather and day type
SELECT trip_date, weekday, day_type, trips, precipitation_mm, rain_level
FROM daily_trips
ORDER BY trip_date;


-- Q1. Average trips per day: rainy vs dry, by day type
SELECT
    day_type,
    CASE WHEN is_rainy THEN 'rainy' ELSE 'dry' END AS weather,
    COUNT(*) AS days,
    ROUND(AVG(trips)) AS avg_trips_per_day
FROM daily_trips
GROUP BY day_type, is_rainy
ORDER BY day_type, weather;


-- Q2. Weekdays only: trips by rain level
SELECT
    rain_level,
    COUNT(*) AS days,
    ROUND(AVG(trips)) AS avg_trips_per_day
FROM daily_trips
WHERE day_type = 'weekday'
GROUP BY rain_level
ORDER BY CASE rain_level WHEN 'dry' THEN 1 WHEN 'light' THEN 2 ELSE 3 END;


-- Q3. Average trips per hour: weekdays vs weekends (holidays excluded)
-- Divided by the number of days of each type, so groups are comparable.
WITH n AS (
    SELECT day_type, COUNT(*) AS n_days
    FROM daily_trips
    GROUP BY day_type
)
SELECT
    h.hour,
    ROUND(SUM(CASE WHEN h.day_type = 'weekday' THEN h.trips END) * 1.0
          / (SELECT n_days FROM n WHERE day_type = 'weekday')) AS weekday_avg,
    ROUND(SUM(CASE WHEN h.day_type = 'weekend' THEN h.trips END) * 1.0
          / (SELECT n_days FROM n WHERE day_type = 'weekend')) AS weekend_avg
FROM hourly_trips h
GROUP BY h.hour
ORDER BY h.hour;


-- Q4. Top 10 departure stations: rank and share of all trips
WITH station_trips AS (
    SELECT
        s.station_name,
        COALESCE(s.city, 'unverified') AS city,
        COUNT(*) AS trips
    FROM trips t
    JOIN stations s ON t.departure_station_id = s.station_id
    GROUP BY s.station_id
),
ranked AS (
    SELECT
        station_name,
        city,
        trips,
        RANK() OVER (ORDER BY trips DESC) AS rank,
        ROUND(100.0 * trips / SUM(trips) OVER (), 2) AS share_pct
    FROM station_trips
)
SELECT rank, station_name, city, trips, share_pct
FROM ranked
WHERE rank <= 10
ORDER BY rank;


-- Q4b. Top 3 stations in each city
WITH station_trips AS (
    SELECT
        s.station_name,
        COALESCE(s.city, 'unverified') AS city,
        COUNT(*) AS trips
    FROM trips t
    JOIN stations s ON t.departure_station_id = s.station_id
    GROUP BY s.station_id
),
ranked AS (
    SELECT
        city,
        station_name,
        trips,
        RANK() OVER (PARTITION BY city ORDER BY trips DESC) AS rank_in_city
    FROM station_trips
)
SELECT city, rank_in_city, station_name, trips
FROM ranked
WHERE rank_in_city <= 3
  AND city <> 'unverified'
ORDER BY city, rank_in_city;


-- Q5. Trips per day with a 7-day moving average
-- The average is shown only when the window has a full 7 days.
SELECT
    trip_date,
    trips,
    precipitation_mm,
    CASE
        WHEN COUNT(*) OVER last7 = 7
        THEN ROUND(AVG(trips) OVER last7)
    END AS avg_7d
FROM daily_trips
WINDOW last7 AS (ORDER BY trip_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
ORDER BY trip_date;