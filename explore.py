import pandas as pd

def normalize(s):
    """Replace non-breaking spaces and trim whitespace."""
    return s.str.replace("\xa0", " ").str.strip()

# 1.Read CSV as table (DataFrame); Trips data
trips = pd.read_csv("data/2025-06.csv")

# 1.1 first 5 rows of the table
print(trips.head())

# 1.2. Size: how many rows and columns
print(trips.shape)

# 1.3. Columns and their types
print(trips.dtypes)

# 1.4. Missing values: how many empty values in each column
print(trips.isna().sum())

# 1.5. Basic statistics for numbers: min, max, mean
print(trips.describe())

# Numbers without scientific notation (e+06)
pd.set_option("display.float_format", "{:.0f}".format)
 
# 1.6. Check for negative or zero distances, and very long distances or durations
print("Negative distance:", (trips["Covered distance (m)"] < 0).sum())
print("Zero distance:", (trips["Covered distance (m)"] == 0).sum())
print("Distance > 50 km:", (trips["Covered distance (m)"] > 50_000).sum())
print("Duration < 60 sec:", (trips["Duration (sec.)"] < 60).sum())
print("Duration > 5 h:", (trips["Duration (sec.)"] > 5 * 3600).sum())
print("Duplicates:", trips.duplicated().sum())

# 1.7. Check for Departure and Return columns without time (only date)
no_time_dep = ~trips["Departure"].str.contains("T")
no_time_ret = ~trips["Return"].str.contains("T")

print("Departure without time:", no_time_dep.sum())
print("Return without time:", no_time_ret.sum())
print(trips[no_time_dep | no_time_ret].head())

# 1.8. Check for departures at 00:00:00–00:00:09 (midnight)
near_midnight = trips["Departure"].str.contains("T00:00:0")
print("Departures at 00:00:00–00:00:09 with time:", near_midnight.sum())


# 1.10. What are the exact times of departures that contain T00:00:0?

print(trips.loc[near_midnight, "Departure"].str[11:].value_counts().sort_index())

# 1.11. Is it exactly T00:00:00 or T00:00:01, etc.?
print("Exactly T00:00:00:", trips["Departure"].str.endswith("T00:00:00").sum())

# 1.12. How accurate is the calculation of Return − Duration on normal rows?
fmt = "%Y-%m-%dT%H:%M:%S"
dep = pd.to_datetime(trips["Departure"], format=fmt, errors="coerce")
ret = pd.to_datetime(trips["Return"], format=fmt, errors="coerce")
diff = (dep - (ret - pd.to_timedelta(trips["Duration (sec.)"], unit="s"))).dt.total_seconds()
print(diff.describe())
print("Within 10 sec:", (diff.abs() <= 10).mean())

# 2. Weather data
weather = pd.read_csv("data/weather-2025-06.csv")
print(weather.head())
print(weather.dtypes)
print(weather.isna().sum())

# 3. Stations data
stations = pd.read_csv("data/stations.csv")
print(stations.head())
print(stations.dtypes)


# 4. Compare station IDs and names between trips and stations

print(stations.columns)           
print(stations["Kaupunki"].value_counts())


print(trips["Departure station id"].head().tolist())
print(stations["ID"].head().tolist())


# 4.1. Unique pairs of station IDs and names in trips
pairs = (
    trips[["Departure station id", "Departure station name"]]
    .drop_duplicates()
    .rename(columns={"Departure station id": "trip_id",
                     "Departure station name": "trip_name"})
)
pairs["id_num"] = pd.to_numeric(pairs["trip_id"], errors="coerce")

# 4.2. How many IDs have several names?
print("IDs with several names:",
      (pairs.groupby("trip_id")["trip_name"].nunique() > 1).sum())

# 4.3. Join по ID → names match?
by_id = pairs.merge(stations[["ID", "Nimi", "Name"]],
                    left_on="id_num", right_on="ID", how="left")
by_id["name_match"] = (by_id["trip_name"] == by_id["Nimi"]) | \
                      (by_id["trip_name"] == by_id["Name"])

print("Stations in trips:", len(by_id))
print("Found by ID:", by_id["ID"].notna().sum())
print("Same name:", by_id["name_match"].sum())
print(by_id.loc[by_id["ID"].notna() & ~by_id["name_match"],
                ["trip_id", "trip_name", "Nimi"]].head(10))

# 4.4. Join by name → IDs match?
by_name = pairs.merge(stations[["ID", "Nimi"]],
                      left_on="trip_name", right_on="Nimi", how="inner")
print("Found by name:", len(by_name))
print("Same ID:", (by_name["id_num"] == by_name["ID"]).sum())
print(by_name.loc[by_name["id_num"] != by_name["ID"],
                  ["trip_id", "trip_name", "ID"]].head(10))

# 4.5. Normalize names and check if trip name starts with station name
by_id["trip_name_n"] = normalize(by_id["trip_name"])
by_id["ref_name_n"] = normalize(by_id["Nimi"])

by_id["valid"] = [
    isinstance(r, str) and (t == r or t.startswith(r))
    for t, r in zip(by_id["trip_name_n"], by_id["ref_name_n"])
]

print("Valid matches:", by_id["valid"].sum())   # ожидаем 443

# Map cities to stations
stations["city"] = stations["Kaupunki"].str.strip().replace("", "Helsinki")
valid = by_id[by_id["valid"]].merge(stations[["ID", "city"]], on="ID")
city_map = dict(zip(valid["trip_id"], valid["city"]))

trips["city"] = trips["Departure station id"].map(city_map)
print(trips["city"].value_counts(normalize=True, dropna=False))


print(trips["city"].value_counts(dropna=False))

bad = by_id[by_id["ID"].notna() & ~by_id["valid"]]
for t, r in zip(bad["trip_name"], bad["Nimi"]):
    print(repr(t), "|", repr(r))  


# 4.6. Non-breaking spaces in station names
for col in ["Departure station name", "Return station name"]:
    n = trips[col].str.contains("\xa0").sum()
    print(f"{col}: {n} trips with \\xa0")

# 4.7. Which station names contain \xa0?
print(trips.loc[trips["Departure station name"].str.contains("\xa0"),
                "Departure station name"].unique())

# 4.8. Non-numeric station IDs
for col in ["Departure station id", "Return station id"]:
    ids = trips[col]
    bad = ids[pd.to_numeric(ids, errors="coerce").isna()]
    print(col, bad.value_counts().to_dict())

    