-- Q0. Daily trips around Midsummer (Juhannus 2025: Eve = Fri 20.6, Day = Sat 21.6)
SELECT
    t.trip_date,
    CASE strftime('%w', t.trip_date)
        WHEN '0' THEN 'Sun' WHEN '1' THEN 'Mon' WHEN '2' THEN 'Tue'
        WHEN '3' THEN 'Wed' WHEN '4' THEN 'Thu' WHEN '5' THEN 'Fri'
        WHEN '6' THEN 'Sat'
    END AS weekday,
    COUNT(*) AS trips,
    w.precipitation_mm
FROM trips t
JOIN weather w ON t.trip_date = w.date
WHERE t.trip_date BETWEEN '2025-06-09' AND '2025-06-29'
GROUP BY t.trip_date
ORDER BY t.trip_date;

-- Q1. Average trips per day: rainy vs dry, weekdays vs weekends
-- Rainy day = precipitation >= 1 mm (see pipeline.py)
-- Midsummer (Fri 20.6 – Sun 22.6.2025) is a separate group:
-- people leave the city; even dry Sunday 22.6 had ~40% fewer trips.

WITH daily AS (
    SELECT
        t.trip_date,
        COUNT(*) AS trips,
        w.is_rainy,
                CASE
            WHEN t.trip_date BETWEEN '2025-06-20' AND '2025-06-22' THEN 'holiday'
            WHEN strftime('%w', t.trip_date) IN ('0', '6') THEN 'weekend'
            ELSE 'weekday'
        END AS day_type
    FROM trips t
    JOIN weather w ON t.trip_date = w.date
    GROUP BY t.trip_date
)
SELECT
    day_type,
    CASE WHEN is_rainy THEN 'rainy' ELSE 'dry' END AS weather,
    COUNT(*) AS days,
    ROUND(AVG(trips)) AS avg_trips_per_day
FROM daily
GROUP BY day_type, is_rainy
ORDER BY day_type, weather;


-- Q2. Weekdays only: trips by rain intensity
-- Holidays excluded. Buckets: dry (< 1 mm), light (1–5 mm), heavy (> 5 mm)
WITH daily AS (
    SELECT
        t.trip_date,
        COUNT(*) AS trips,
        w.precipitation_mm
    FROM trips t
    JOIN weather w ON t.trip_date = w.date
    WHERE strftime('%w', t.trip_date) NOT IN ('0', '6')
      AND t.trip_date NOT BETWEEN '2025-06-20' AND '2025-06-22'
    GROUP BY t.trip_date
)
SELECT
    CASE
        WHEN precipitation_mm < 1 THEN '1_dry (< 1 mm)'
        WHEN precipitation_mm <= 5 THEN '2_light (1–5 mm)'
        ELSE '3_heavy (> 5 mm)'
    END AS rain,
    COUNT(*) AS days,
    ROUND(AVG(trips)) AS avg_trips_per_day
FROM daily
GROUP BY rain
ORDER BY rain;

-- Q3. Average trips per hour: weekdays vs weekends
-- Midsummer (20–22 June) excluded.
-- Divided by the number of days of each type, so groups are comparable.
WITH trips_typed AS (
    SELECT
        strftime('%H', departure) AS hour,
        trip_date,
        CASE
            WHEN strftime('%w', trip_date) IN ('0', '6') THEN 'weekend'
            ELSE 'weekday'
        END AS day_type
    FROM trips
    WHERE trip_date NOT BETWEEN '2025-06-20' AND '2025-06-22'
),
days AS (
    SELECT day_type, COUNT(DISTINCT trip_date) AS n_days
    FROM trips_typed
    GROUP BY day_type
)
SELECT
    hour,
    ROUND(SUM(day_type = 'weekday') * 1.0
          / (SELECT n_days FROM days WHERE day_type = 'weekday')) AS weekday_avg,
    ROUND(SUM(day_type = 'weekend') * 1.0
          / (SELECT n_days FROM days WHERE day_type = 'weekend')) AS weekend_avg
FROM trips_typed
GROUP BY hour
ORDER BY hour;