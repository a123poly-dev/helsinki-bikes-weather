import pandas as pd

TRIPS_FILE = "data/2025-06.csv"


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


def main():
    print("Extract trips...")
    trips = extract_trips(TRIPS_FILE)

    print("Clean trips...")
    trips = clean_trips(trips)

    print(trips.dtypes)
    # Next steps: extract_weather(), load_to_sqlite()


if __name__ == "__main__":
    main()

    