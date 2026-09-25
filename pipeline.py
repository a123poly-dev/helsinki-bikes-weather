import pandas as pd

TRIPS_FILE = "data/2025-06.csv"
WEATHER_FILE = "data/weather-2025-06.csv"


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

    rules = {
        "invalid date": df["Departure"].isna() | df["Return"].isna(),
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


def main():
    print("Extract trips...")
    trips = extract_trips(TRIPS_FILE)

    print("Clean trips...")
    trips = clean_trips(trips)

    print("Extract weather...")
    weather = extract_weather(WEATHER_FILE)

    print("Clean weather...")
    weather = clean_weather(weather)
    print(weather.head())

    # Next steps: load_to_sqlite()


if __name__ == "__main__":
    main()

    