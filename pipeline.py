import sqlite3

import pandas as pd

TRIPS_FILE = "data/2025-06.csv"
WEATHER_FILE = "data/weather-2025-06.csv"
STATIONS_FILE = "data/stations.csv"
DB_FILE = "data/bikes.db"
MANUAL_STATIONS_FILE = "reference/stations_manual.csv"


def normalize(s):
    """Replace non-breaking spaces and trim whitespace."""
    return s.str.replace("\xa0", " ").str.strip()

def extract_trips(path):
    """Read raw trips from CSV."""
    return pd.read_csv(path)


def clean_trips(df):
    """Fix data types, remove invalid trips, add flags."""
    before = len(df)

    fmt = "%Y-%m-%dT%H:%M:%S"
    raw = df["Departure"]
    date_only = ~raw.str.contains("T")

    # Date without time = exactly midnight (export bug)
    raw = raw.where(~date_only, raw + "T00:00:00")

    df["Departure"] = pd.to_datetime(raw, format=fmt, errors="coerce")
    df["Return"] = pd.to_datetime(df["Return"], format=fmt, errors="coerce")
    df["departure_fixed"] = date_only
    print(f"  departure without time (set to 00:00:00): {date_only.sum()}")

    # Station names: remove non-breaking spaces
    for col in ["Departure station name", "Return station name"]:
        n = df[col].str.contains("\xa0").sum()
        df[col] = normalize(df[col])
        print(f"  {col}: \\xa0 fixed in {n} rows")

    rules = {
        "invalid date": df["Departure"].isna() | df["Return"].isna(),
        "returned to workshop (997)": df["Return station id"] == "997",
        "distance <= 0": df["Covered distance (m)"] <= 0,
        "distance > 50 km": df["Covered distance (m)"] > 50_000,
        "duration < 60 sec": df["Duration (sec.)"] < 60,
        "duration > 5 h": df["Duration (sec.)"] > 5 * 3600,
    }


    bad = pd.Series(False, index=df.index)
    for name, mask in rules.items():
        print(f"  {name}: {mask.sum()}")
        bad |= mask

    df = df[~bad].copy()

    # Add a new column to indicate trips over 1 hour
    df["over_limit"] = df["Duration (sec.)"] > 3600

    gap = ((df["Return"] - df["Departure"]).dt.total_seconds() - df["Duration (sec.)"]).abs()
    df["duration_mismatch"] = gap > 60

    print(f"  duration mismatch > 60 sec (flagged): {df['duration_mismatch'].sum()}")

    removed = before - len(df)
    print(f"Removed {removed} of {before} rows ({removed / before:.1%})")
    return df


def extract_weather(path):
    """Read daily weather observations from FMI CSV."""
    return pd.read_csv(path)


def clean_weather(df):
    """Build date column, fix FMI codes, rename columns."""
    df["date"] = pd.to_datetime(df[["Year", "Month", "Day"]]).dt.date

    df = df.rename(columns={
        "Precipitation amount [mm]": "precipitation_mm",
        "Average temperature [°C]": "temp_avg_c",
        "Maximum temperature [°C]": "temp_max_c",
    })

    # FMI: -1 means no precipitation
    no_rain = df["precipitation_mm"] == -1
    df.loc[no_rain, "precipitation_mm"] = 0
    print(f"  precipitation -1 → 0: {no_rain.sum()}")

    # Rainy day: at least 1 mm
    df["is_rainy"] = df["precipitation_mm"] >= 1

    # Checks: one row per day, no gaps
    assert df["date"].is_unique, "Duplicate dates in weather data"
    print(f"  days: {len(df)}, rainy: {df['is_rainy'].sum()}")

    return df[["date", "precipitation_mm", "temp_avg_c", "temp_max_c", "is_rainy"]]

def extract_stations(path):
    """Read stations from CSV."""
    return pd.read_csv(path)

def build_stations(trips, ref, manual):
    """Station list from trips, enriched from the reference
    only where both ID and name match. IDs are kept as text codes."""
    dep = trips[["Departure station id", "Departure station name"]]
    dep.columns = ["station_id", "station_name"]
    ret = trips[["Return station id", "Return station name"]]
    ret.columns = ["station_id", "station_name"]
    st = pd.concat([dep, ret]).drop_duplicates("station_id").copy()

    # Numeric version only for matching with the reference ('044' -> 44)
    st["id_num"] = pd.to_numeric(st["station_id"], errors="coerce")

    ref = ref.rename(columns={
        "ID": "ref_id", "Nimi": "ref_name", "Kaupunki": "city",
        "Kapasiteet": "capacity", "x": "lon", "y": "lat",
    })
    ref["ref_name"] = normalize(ref["ref_name"])
    ref["city"] = ref["city"].str.strip().replace("", "Helsinki")

    st = st.merge(ref[["ref_id", "ref_name", "city", "capacity", "lon", "lat"]],
                  left_on="id_num", right_on="ref_id", how="left")

    # Accept reference data only if names match (reference names can be truncated)
    st["verified"] = [
        isinstance(r, str) and (t == r or t.startswith(r))
        for t, r in zip(st["station_name"], st["ref_name"])
    ]
    st.loc[~st["verified"], ["city", "capacity", "lon", "lat"]] = None

    # Manual fixes for stations missing or outdated in the 2021 reference
    manual = manual.rename(columns={"city": "manual_city"})
    st = st.merge(manual[["station_id", "manual_city"]], on="station_id", how="left")
    fill = ~st["verified"] & st["manual_city"].notna()
    st.loc[fill, "city"] = st.loc[fill, "manual_city"]

    st["city_source"] = None
    st.loc[st["verified"], "city_source"] = "reference"
    st.loc[fill, "city_source"] = "manual"
    st = st.drop(columns="manual_city")
    print(f"  city filled manually: {fill.sum()}")

    print(f"  stations: {len(st)}, verified: {st['verified'].sum()}")
    return st.drop(columns=["id_num", "ref_id", "ref_name"])


def load_to_sqlite(trips, weather, stations, db_path):
    """Load all tables into SQLite. Safe to re-run."""
    trips = trips.rename(columns={
        "Departure": "departure",
        "Return": "return_time",
        "Departure station id": "departure_station_id",
        "Return station id": "return_station_id",
        "Covered distance (m)": "distance_m",
        "Duration (sec.)": "duration_sec",
    })

    trips["trip_date"] = trips["departure"].dt.date
    trips = trips.drop(columns=["Departure station name", "Return station name"])

    conn = sqlite3.connect(db_path)
    trips.to_sql("trips", conn, if_exists="replace", index=False)
    stations.to_sql("stations", conn, if_exists="replace", index=False)
    weather.to_sql("weather", conn, if_exists="replace", index=False)

    for table in ["trips", "stations", "weather"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {n} rows")
    conn.close()


def main():
    print("Extract trips...")
    trips = extract_trips(TRIPS_FILE)

    print("Clean trips...")
    trips = clean_trips(trips)

    print("Extract weather...")
    weather = extract_weather(WEATHER_FILE)

    print("Clean weather...")
    weather = clean_weather(weather)

    print("Extract stations...")
    ref = extract_stations(STATIONS_FILE)

    print("Build stations...")
    manual = pd.read_csv(MANUAL_STATIONS_FILE, dtype={"station_id": str})
    stations = build_stations(trips, ref, manual)

    print("Load to SQLite...")
    load_to_sqlite(trips, weather, stations, DB_FILE)
   
# Next steps: load_to_sqlite()

if __name__ == "__main__":
    main()

    