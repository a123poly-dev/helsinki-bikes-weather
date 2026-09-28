"""Tests for cleaning and station validation in pipeline.py.
Run from the project root: python -m pytest
"""
import pandas as pd

from pipeline import build_stations, clean_trips, clean_weather

COLUMNS = [
    "Departure", "Return",
    "Departure station id", "Departure station name",
    "Return station id", "Return station name",
    "Covered distance (m)", "Duration (sec.)",
]


def make_trips(rows):
    """Build a raw trips table like the HSL CSV (IDs are text)."""
    return pd.DataFrame(rows, columns=COLUMNS)


# A normal 10-minute trip; other rows change one field to break a rule
VALID = ["2025-06-10T08:00:00", "2025-06-10T08:10:00",
         "044", "Sörnäinen (M)", "049", "Annankatu", 2000, 600]


def with_changes(**changes):
    row = dict(zip(COLUMNS, VALID))
    row.update(changes)
    return [row[c] for c in COLUMNS]


def test_clean_trips_removes_invalid_rows():
    raw = make_trips([
        VALID,
        with_changes(**{"Covered distance (m)": 0}),                 # zero distance
        with_changes(**{"Covered distance (m)": -4_294_042}),        # negative distance
        with_changes(**{"Covered distance (m)": 60_000}),            # > 50 km
        with_changes(**{"Duration (sec.)": 30}),                     # < 60 sec
        with_changes(**{"Duration (sec.)": 6 * 3600}),               # > 5 h
        with_changes(**{"Return station id": "997"}),                # workshop
        with_changes(Return="not a date"),                           # invalid date
    ])

    result = clean_trips(raw)

    assert len(result) == 1
    assert result.iloc[0]["Departure station id"] == "044"


def test_date_without_time_is_midnight():
    raw = make_trips([
        with_changes(Departure="2025-06-27", Return="2025-06-27T00:03:06",
                     **{"Duration (sec.)": 180}),
    ])

    result = clean_trips(raw)

    assert result.iloc[0]["Departure"] == pd.Timestamp("2025-06-27 00:00:00")
    assert result.iloc[0]["departure_fixed"]


def test_station_names_are_normalized():
    raw = make_trips([with_changes(**{"Departure station name": "Vallilan\xa0varikko "})])

    result = clean_trips(raw)

    assert result.iloc[0]["Departure station name"] == "Vallilan varikko"


def test_flags_are_set_but_rows_kept():
    raw = make_trips([
        VALID,
        with_changes(Return="2025-06-10T10:00:00", **{"Duration (sec.)": 2 * 3600}),  # 2 h
        with_changes(Return="2025-06-10T20:00:00"),  # 12 h by time, 10 min by duration
    ])

    result = clean_trips(raw)

    assert len(result) == 3
    assert list(result["over_limit"]) == [False, True, False]
    assert list(result["duration_mismatch"]) == [False, False, True]


def test_clean_weather_rain_levels():
    raw = pd.DataFrame({
        "Year": [2025] * 5,
        "Month": [6] * 5,
        "Day": [1, 2, 3, 4, 5],
        "Precipitation amount [mm]": [-1, 0.6, 1.0, 5.0, 5.1],
        "Average temperature [°C]": [15] * 5,
        "Maximum temperature [°C]": [20] * 5,
    })

    result = clean_weather(raw)

    assert list(result["precipitation_mm"]) == [0, 0.6, 1.0, 5.0, 5.1]  # -1 -> 0
    assert list(result["rain_level"]) == ["dry", "dry", "light", "light", "heavy"]
    assert list(result["is_rainy"]) == [False, False, True, True, True]


def test_build_stations_validates_ids_by_name():
    trips = make_trips([
        # Leading zero in trips, number in the reference: same station
        with_changes(**{"Departure station id": "044", "Departure station name": "Sörnäinen (M)",
                        "Return station id": "541",
                        "Return station name": "Aalto-yliopisto (M), Korkeakouluaukio"}),
        # ID reused for another station in the reference
        with_changes(**{"Departure station id": "132", "Departure station name": "Urhea-kampus",
                        "Return station id": "*40", "Return station name": "Puotila"}),
    ])
    ref = pd.DataFrame({
        "ID": [44, 541, 132],
        "Nimi": ["Sörnäinen (M)", "Aalto-yliopisto (M), Korkea", "Hollolantie"],  # truncated name
        "Kaupunki": [" ", "Espoo", " "],
        "Kapasiteet": [20, 30, 10],
        "x": [24.96, 24.83, 24.95],
        "y": [60.19, 60.18, 60.21],
    })
    manual = pd.DataFrame({"station_id": ["132", "*40"], "city": ["Helsinki", "Helsinki"]})

    result = build_stations(trips, ref, manual).set_index("station_id")

    assert result.loc["044", "verified"] and result.loc["044", "city"] == "Helsinki"
    assert result.loc["541", "verified"] and result.loc["541", "city"] == "Espoo"
    assert not result.loc["132", "verified"]                   # name does not match
    assert result.loc["132", "city_source"] == "manual"
    assert result.loc["*40", "city"] == "Helsinki"             # non-numeric ID kept as text