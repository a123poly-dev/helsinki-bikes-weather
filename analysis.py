import os
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

from pipeline import DB_FILE, RAIN_THRESHOLD_MM, HEAVY_RAIN_MM

OUT_DIR = "images"

# Colors (validated reference palette: slot 1 blue, slot 2 orange)
BLUE = "#2a78d6"
LIGHT_BLUE = "#b7d3f6"  # same hue, light step: averages behind the dots
ORANGE = "#eb6834"
GRAY = "#c9c7bf"        # neutral bars (context)
HOLIDAY_BG = "#f0efec"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e2dc"
SURFACE = "#fcfcfb"

thousands = FuncFormatter(lambda x, _: f"{x:,.0f}")


def period_label(dates):
    """'June 2025' for one month, 'Jun 2025 – Aug 2025' for several."""
    start, end = dates.min(), dates.max()
    if (start.year, start.month) == (end.year, end.month):
        return start.strftime("%B %Y")
    return f"{start:%b %Y} – {end:%b %Y}"


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
    """Weekday trips by rain level: every day as a dot, the average as a bar."""
    df = pd.read_sql(
        "SELECT trip_date, trips, rain_level FROM daily_trips WHERE day_type = ?",
        conn, params=("weekday",), parse_dates=["trip_date"],
    )
    levels = ["dry", "light", "heavy"]
    names = {
        "dry": f"Dry\n< {RAIN_THRESHOLD_MM:g} mm",
        "light": f"Light rain\n{RAIN_THRESHOLD_MM:g}–{HEAVY_RAIN_MM:g} mm",
        "heavy": f"Heavy rain\n> {HEAVY_RAIN_MM:g} mm",
    }
    stats = df.groupby("rain_level")["trips"].agg(["mean", "count", "max"]).reindex(levels)
    base = stats.loc["dry", "mean"]
    top = df["trips"].max()

    fig, ax = plt.subplots(figsize=(7, 4.8), facecolor=SURFACE)
    ax.bar(range(3), stats["mean"], color=LIGHT_BLUE, width=0.55, zorder=1)
    for i, level in enumerate(levels):
        values = df.loc[df["rain_level"] == level].sort_values("trip_date")["trips"]
        jitter = np.linspace(-0.15, 0.15, len(values)) if len(values) > 1 else [0]
        ax.scatter(i + np.asarray(jitter), values, s=40, color=BLUE,
                   edgecolor=SURFACE, linewidth=1.5, zorder=3)

        mean = stats.loc[level, "mean"]
        effect = "" if level == "dry" else f"  (−{(base - mean) / base:.0%})"
        label_y = max(mean, stats.loc[level, "max"]) + top * 0.03
        ax.text(i, label_y, f"avg {mean:,.0f}{effect}", ha="center", va="bottom",
                fontsize=10, color=TEXT)

    ax.set_xticks(range(3))
    ax.set_xticklabels([f"{names[l]}\n{int(stats.loc[l, 'count'])} days" for l in levels])
    ax.set_ylim(0, top * 1.2)
    ax.legend(
        handles=[Patch(color=LIGHT_BLUE, label="Average"),
                 Line2D([0], [0], marker="o", color="none", markerfacecolor=BLUE,
                        markeredgecolor=SURFACE, markersize=8, label="One weekday")],
        frameon=False, loc="upper right", ncol=2, fontsize=10, labelcolor=TEXT,
    )
    style(ax, "Weekday trips drop as rain gets heavier",
          f"Trips per weekday, {period_label(df['trip_date'])} (holidays excluded)")
    save(fig, "rain_intensity.png")


def chart_hourly(conn):
    """Average trips per hour: weekdays vs weekends."""
    df = pd.read_sql("""
        WITH n AS (
            SELECT day_type, COUNT(*) AS n_days
            FROM daily_trips
            GROUP BY day_type
        )
        SELECT h.hour, h.day_type, SUM(h.trips) * 1.0 / n.n_days AS avg_trips
        FROM hourly_trips h
        JOIN n ON h.day_type = n.day_type
        WHERE h.day_type IN (?, ?)
        GROUP BY h.hour, h.day_type
        ORDER BY h.hour
    """, conn, params=("weekday", "weekend"))
    dates = pd.read_sql("SELECT trip_date FROM daily_trips", conn, parse_dates=["trip_date"])
    wide = df.pivot(index="hour", columns="day_type", values="avg_trips")

    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor=SURFACE)
    for col, color, label in [("weekday", BLUE, "Weekdays"), ("weekend", ORANGE, "Weekends")]:
        ax.plot(wide.index, wide[col], color=color, linewidth=2, label=label)

    ax.set_xticks(range(0, 24, 3))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 3)])
    ax.set_xlim(0, 23)
    ax.set_ylim(0, None)
    ax.legend(frameon=False, loc="upper left", fontsize=10, labelcolor=TEXT)
    style(ax, "Weekday commute peaks vs weekend afternoons",
          f"Average trips per hour of departure, {period_label(dates['trip_date'])} "
          "(holidays excluded)")
    save(fig, "hourly.png")


def chart_daily(conn):
    """Trips per day, rainy days highlighted, 7-day moving average, holidays shaded."""
    df = pd.read_sql("""
        SELECT
            trip_date,
            trips,
            is_rainy,
            day_type,
            CASE WHEN COUNT(*) OVER last7 = 7
                 THEN AVG(trips) OVER last7 END AS avg_7d
        FROM daily_trips
        WINDOW last7 AS (ORDER BY trip_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
        ORDER BY trip_date
    """, conn, parse_dates=["trip_date"])
    holidays = pd.read_sql(
        "SELECT date, name FROM holidays WHERE date BETWEEN ? AND ?",
        conn, params=(f"{df['trip_date'].min():%Y-%m-%d}", f"{df['trip_date'].max():%Y-%m-%d}"),
        parse_dates=["date"],
    )
    top = df["trips"].max()
    half_day = pd.Timedelta(hours=12)

    fig, ax = plt.subplots(figsize=(10, 4.5), facecolor=SURFACE)
    for day in holidays["date"]:
        ax.axvspan(day - half_day, day + half_day, color=HOLIDAY_BG, linewidth=0, zorder=0)
    for name, group in holidays.groupby("name"):
        ax.text(group["date"].mean(), top * 1.07, name, ha="center", fontsize=9, color=TEXT_2)

    colors = [BLUE if rainy else GRAY for rainy in df["is_rainy"]]
    ax.bar(df["trip_date"], df["trips"], color=colors, width=0.8, zorder=2)
    ax.plot(df["trip_date"], df["avg_7d"], color=ORANGE, linewidth=2, zorder=3)

    ax.set_xlim(df["trip_date"].min() - pd.Timedelta(hours=14),
                df["trip_date"].max() + pd.Timedelta(hours=14))
    ax.xaxis.set_major_locator(mdates.DayLocator(bymonthday=[1, 8, 15, 22, 29]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%-d %b"))
    ax.set_ylim(0, top * 1.15)
    ax.legend(
        handles=[Patch(color=GRAY, label="Dry day"),
                 Patch(color=BLUE, label=f"Rainy day (≥ {RAIN_THRESHOLD_MM:g} mm)"),
                 Line2D([0], [0], color=ORANGE, linewidth=2, label="7-day average")],
        frameon=False, loc="upper right", ncol=3, fontsize=10, labelcolor=TEXT,
        bbox_to_anchor=(1, 1.12),
    )
    style(ax, "Rainy days and holidays pull the weekly average down",
          f"Trips per day, {period_label(df['trip_date'])}")
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