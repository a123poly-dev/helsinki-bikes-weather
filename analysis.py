import os
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
import pandas as pd

DB_FILE = "data/bikes.db"
OUT_DIR = "images"

# Colors (validated reference palette: slot 1 blue, slot 2 orange)
BLUE = "#2a78d6"
ORANGE = "#eb6834"
GRAY = "#c9c7bf"       # neutral bars (context)
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e2dc"
SURFACE = "#fcfcfb"

HOLIDAY_START, HOLIDAY_END = "2025-06-20", "2025-06-22"

thousands = FuncFormatter(lambda x, _: f"{x:,.0f}")


def style(ax, title, subtitle):
    """Recessive axes and grid, title + subtitle in text colors."""
    ax.set_facecolor(SURFACE)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT_2, length=0, labelsize=10)
    ax.yaxis.grid(True, color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(thousands)
    ax.set_title(title, loc="left", fontsize=14, fontweight="bold", color=TEXT, pad=28)
    ax.text(0, 1.03, subtitle, transform=ax.transAxes, fontsize=10, color=TEXT_2)


def save(fig, name):
    path = os.path.join(OUT_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    print(f"  saved {path}")


def chart_rain_intensity(conn):
    """Q2: weekday trips by rain intensity."""
    df = pd.read_sql(f"""
        WITH daily AS (
            SELECT t.trip_date, COUNT(*) AS trips, w.precipitation_mm
            FROM trips t
            JOIN weather w ON t.trip_date = w.date
            WHERE strftime('%w', t.trip_date) NOT IN ('0', '6')
              AND t.trip_date NOT BETWEEN '{HOLIDAY_START}' AND '{HOLIDAY_END}'
            GROUP BY t.trip_date
        )
        SELECT
            CASE
                WHEN precipitation_mm < 1 THEN 1
                WHEN precipitation_mm <= 5 THEN 2
                ELSE 3
            END AS bucket,
            COUNT(*) AS days,
            AVG(trips) AS avg_trips
        FROM daily
        GROUP BY bucket
        ORDER BY bucket
    """, conn)

    names = {1: "Dry\n< 1 mm", 2: "Light rain\n1–5 mm", 3: "Heavy rain\n> 5 mm"}
    labels = [f"{names[b]}\n{d} days" for b, d in zip(df["bucket"], df["days"])]
    base = df["avg_trips"].iloc[0]

    fig, ax = plt.subplots(figsize=(7, 4.5), facecolor=SURFACE)
    bars = ax.bar(labels, df["avg_trips"], color=BLUE, width=0.55)
    for bar, value in zip(bars, df["avg_trips"]):
        effect = "" if value == base else f"  (−{(base - value) / base:.0%})"
        ax.text(bar.get_x() + bar.get_width() / 2, value + base * 0.02,
                f"{value:,.0f}{effect}", ha="center", va="bottom",
                fontsize=10, color=TEXT)
    ax.set_ylim(0, base * 1.15)
    style(ax, "Weekday trips drop as rain gets heavier",
          "Average trips per weekday, June 2025 (Midsummer excluded)")
    save(fig, "rain_intensity.png")


def chart_hourly(conn):
    """Q3: average trips per hour, weekdays vs weekends."""
    df = pd.read_sql(f"""
        WITH trips_typed AS (
            SELECT
                CAST(strftime('%H', departure) AS INTEGER) AS hour,
                trip_date,
                CASE WHEN strftime('%w', trip_date) IN ('0', '6')
                     THEN 'weekend' ELSE 'weekday' END AS day_type
            FROM trips
            WHERE trip_date NOT BETWEEN '{HOLIDAY_START}' AND '{HOLIDAY_END}'
        ),
        days AS (
            SELECT day_type, COUNT(DISTINCT trip_date) AS n_days
            FROM trips_typed GROUP BY day_type
        )
        SELECT t.hour, t.day_type, COUNT(*) * 1.0 / d.n_days AS avg_trips
        FROM trips_typed t
        JOIN days d ON t.day_type = d.day_type
        GROUP BY t.hour, t.day_type
        ORDER BY t.hour
    """, conn)
    wide = df.pivot(index="hour", columns="day_type", values="avg_trips")

    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor=SURFACE)
    for col, color, label in [("weekday", BLUE, "Weekdays"), ("weekend", ORANGE, "Weekends")]:
        ax.plot(wide.index, wide[col], color=color, linewidth=2, label=label)
        ax.text(23.3, wide[col].iloc[-1], label, color=TEXT, fontsize=10, va="center")

    ax.set_xticks(range(0, 24, 3))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 3)])
    ax.set_xlim(0, 23)
    ax.set_ylim(0, None)
    ax.legend(frameon=False, loc="upper left", fontsize=10, labelcolor=TEXT)
    style(ax, "Weekday commute peaks vs weekend afternoons",
          "Average trips per hour of departure, June 2025 (Midsummer excluded)")
    save(fig, "hourly.png")


def chart_daily(conn):
    """Q5: trips per day, rainy days highlighted, 7-day moving average."""
    df = pd.read_sql("""
        WITH daily AS (
            SELECT trip_date, COUNT(*) AS trips
            FROM trips
            GROUP BY trip_date
        )
        SELECT
            d.trip_date,
            d.trips,
            w.is_rainy,
            CASE WHEN COUNT(*) OVER last7 = 7
                 THEN AVG(d.trips) OVER last7 END AS avg_7d
        FROM daily d
        JOIN weather w ON d.trip_date = w.date
        WINDOW last7 AS (ORDER BY d.trip_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
        ORDER BY d.trip_date
    """, conn)
    df["trip_date"] = pd.to_datetime(df["trip_date"])
    colors = [BLUE if r else GRAY for r in df["is_rainy"]]

    fig, ax = plt.subplots(figsize=(10, 4.5), facecolor=SURFACE)
    ax.axvspan(pd.Timestamp(HOLIDAY_START) - pd.Timedelta(hours=12),
               pd.Timestamp(HOLIDAY_END) + pd.Timedelta(hours=12),
               color="#f0efec", zorder=0)
    ax.text(pd.Timestamp("2025-06-21"), df["trips"].max() * 1.07, "Midsummer",
            ha="center", fontsize=9, color=TEXT_2)
    ax.bar(df["trip_date"], df["trips"], color=colors, width=0.8, zorder=2)
    ax.plot(df["trip_date"], df["avg_7d"], color=ORANGE, linewidth=2, zorder=3)

    ax.set_xlim(df["trip_date"].min() - pd.Timedelta(hours=14),
                df["trip_date"].max() + pd.Timedelta(hours=14))
    ax.xaxis.set_major_locator(mdates.DayLocator(bymonthday=[1, 8, 15, 22, 29]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%-d Jun"))
    ax.set_ylim(0, df["trips"].max() * 1.15)
    ax.legend(
        handles=[Patch(color=GRAY, label="Dry day"),
                 Patch(color=BLUE, label="Rainy day (≥ 1 mm)"),
                 Line2D([0], [0], color=ORANGE, linewidth=2, label="7-day average")],
        frameon=False, loc="upper right", ncol=3, fontsize=10, labelcolor=TEXT,
        bbox_to_anchor=(1, 1.12),
    )
    style(ax, "Rainy days and Midsummer pull the weekly average down",
          "Trips per day, June 2025")
    save(fig, "daily.png")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    print("Charts...")
    chart_rain_intensity(conn)
    chart_hourly(conn)
    chart_daily(conn)
    conn.close()


if __name__ == "__main__":
    main()