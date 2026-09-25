import pandas as pd

# Read CSV as table (DataFrame)
df = pd.read_csv("data/2025-06.csv")

# 1. first 5 rows of the table
print(df.head())

# 2. Size: how many rows and columns
print(df.shape)

# 3. Columns and their types
print(df.dtypes)

# 4. Missing values: how many empty values in each column
print(df.isna().sum())

# 5. Basic statistics for numbers: min, max, mean
print(df.describe())

# Numbers without scientific notation (e+06)
pd.set_option("display.float_format", "{:.0f}".format)

# 6. Check for negative or zero distances, and very long distances or durations
print("Negative distance:", (df["Covered distance (m)"] < 0).sum())
print("Zero distance:", (df["Covered distance (m)"] == 0).sum())
print("Distance > 50 km:", (df["Covered distance (m)"] > 50_000).sum())
print("Duration < 60 sec:", (df["Duration (sec.)"] < 60).sum())
print("Duration > 5 h:", (df["Duration (sec.)"] > 5 * 3600).sum())
print("Duplicates:", df.duplicated().sum())

# 7. Check for Departure and Return columns without time (only date)
no_time_dep = ~df["Departure"].str.contains("T")
no_time_ret = ~df["Return"].str.contains("T")

print("Departure without time:", no_time_dep.sum())
print("Return without time:", no_time_ret.sum())
print(df[no_time_dep | no_time_ret].head())

# 8. Check for departures at 00:00:00–00:00:09 (midnight)
near_midnight = df["Departure"].str.contains("T00:00:0")
print("Departures at 00:00:00–00:00:09 with time:", near_midnight.sum())

# 9. Check for departures exactly at 00:00:00
# 10. What are the exact times of departures that contain T00:00:0?
near_midnight = df["Departure"].str.contains("T00:00:0")
print(df.loc[near_midnight, "Departure"].str[11:].value_counts().sort_index())

# 11. Is it exactly T00:00:00 or T00:00:01, etc.?
print("Exactly T00:00:00:", df["Departure"].str.endswith("T00:00:00").sum())

# 12. How accurate is the calculation of Return − Duration on normal rows?
fmt = "%Y-%m-%dT%H:%M:%S"
dep = pd.to_datetime(df["Departure"], format=fmt, errors="coerce")
ret = pd.to_datetime(df["Return"], format=fmt, errors="coerce")
diff = (dep - (ret - pd.to_timedelta(df["Duration (sec.)"], unit="s"))).dt.total_seconds()
print(diff.describe())
print("Within 10 sec:", (diff.abs() <= 10).mean())

import pandas as pd

w = pd.read_csv("data/weather-2025-06.csv")
print(w.head())
print(w.dtypes)
print(w.isna().sum())