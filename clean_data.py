"""
Clean the MTA Daily Ridership and Traffic dataset (long format) and
compute a pre-pandemic baseline.

Input:
  MTA_Daily_Ridership_and_Traffic__Beginning_2020_20260916.csv
    columns: Date, Mode, Count (one row per date x mode)

Baseline method:
  The current daily dataset no longer ships MTA's "% of comparable
  pre-pandemic day" columns. The older (deprecated) wide-format export
  did, for March 2020 through January 9, 2025. Since
      pct = ridership / comparable_2019_day
  the implied 2019 baseline for each mode is ridership / pct. We take
  the median of that implied baseline by mode x month x day-of-week
  across 2022-2024 (once ratios were stable), which reproduces MTA's
  seasonal, weekday-aware baseline closely enough to extend the recovery
  index through 2026.

Output: clean_mta_daily.csv (wide, one row per day)
"""
import numpy as np
import pandas as pd

from config import RAW_DAILY, RAW_LEGACY_DAILY, CLEAN_DAILY


MODE_MAP = {
    "Subway": "subway",
    "Bus": "bus",
    "LIRR": "lirr",
    "MNR": "metro_north",
    "AAR": "access_a_ride",
    "BT": "bridges_tunnels",
    "SIR": "sir",
    "CRZ Entries": "crz_entries",
    "CBD Entries": "cbd_entries",
}
RIDERSHIP_MODES = ["subway", "bus", "lirr", "metro_north", "access_a_ride", "bridges_tunnels", "sir"]

# ---------- 1. Load and reshape the current daily file ----------
raw = pd.read_csv(RAW_DAILY)
raw["Date"] = pd.to_datetime(raw["Date"], format="%m/%d/%Y")
raw["Count"] = raw["Count"].astype(str).str.replace(",", "", regex=False).astype(float)
raw["Mode"] = raw["Mode"].map(MODE_MAP)

wide = raw.pivot_table(index="Date", columns="Mode", values="Count", aggfunc="first").reset_index()
wide.columns.name = None
wide = wide.sort_values("Date").reset_index(drop=True)

wide["year"] = wide["Date"].dt.year
wide["month"] = wide["Date"].dt.month
wide["dow"] = wide["Date"].dt.dayofweek
wide["day_of_week"] = wide["Date"].dt.day_name()
wide["is_weekend"] = wide["dow"] >= 5
wide["congestion_pricing_active"] = wide["Date"] >= pd.Timestamp("2025-01-05")

# ---------- 2. Back out the implied 2019 baseline from the legacy file ----------
legacy = pd.read_csv(RAW_LEGACY_DAILY)
legacy["Date"] = pd.to_datetime(legacy["Date"], format="%m/%d/%Y")

legacy_cols = {
    "subway": ("Subways: Total Estimated Ridership", "Subways: % of Comparable Pre-Pandemic Day"),
    "bus": ("Buses: Total Estimated Ridership", "Buses: % of Comparable Pre-Pandemic Day"),
    "lirr": ("LIRR: Total Estimated Ridership", "LIRR: % of Comparable Pre-Pandemic Day"),
    "metro_north": ("Metro-North: Total Estimated Ridership", "Metro-North: % of Comparable Pre-Pandemic Day"),
    "access_a_ride": ("Access-A-Ride: Total Scheduled Trips", "Access-A-Ride: % of Comparable Pre-Pandemic Day"),
    "bridges_tunnels": ("Bridges and Tunnels: Total Traffic", "Bridges and Tunnels: % of Comparable Pre-Pandemic Day"),
    "sir": ("Staten Island Railway: Total Estimated Ridership", "Staten Island Railway: % of Comparable Pre-Pandemic Day"),
}

implied = pd.DataFrame({"Date": legacy["Date"]})
for mode, (rcol, pcol) in legacy_cols.items():
    r = legacy[rcol].astype(str).str.replace(",", "", regex=False).astype(float)
    p = legacy[pcol].astype(str).str.replace("%", "", regex=False).astype(float) / 100
    implied[mode] = np.where(p > 0, r / p, np.nan)

implied["month"] = implied["Date"].dt.month
implied["dow"] = implied["Date"].dt.dayofweek
stable = implied[(implied["Date"] >= "2022-01-01") & (implied["Date"] <= "2024-12-31")]

baseline = stable.groupby(["month", "dow"])[RIDERSHIP_MODES].median().reset_index()
baseline = baseline.rename(columns={m: f"{m}_baseline" for m in RIDERSHIP_MODES})

# ---------- 3. Attach baseline and compute recovery index ----------
wide = wide.merge(baseline, on=["month", "dow"], how="left")
for m in RIDERSHIP_MODES:
    wide[f"{m}_pct_prepandemic"] = wide[m] / wide[f"{m}_baseline"]

# ---------- 4. Validate against MTA's published ratios where they overlap ----------
check = wide.merge(
    legacy[["Date"] + [pcol for _, pcol in legacy_cols.values()]], on="Date", how="inner"
)
print("Baseline validation (mean abs error vs MTA published ratio, 2022-2024 overlap):")
for mode, (_, pcol) in legacy_cols.items():
    official = check[pcol].astype(str).str.replace("%", "", regex=False).astype(float) / 100
    mask = (check["Date"] >= "2022-01-01")
    mae = (check.loc[mask, f"{mode}_pct_prepandemic"] - official[mask]).abs().mean()
    print(f"  {mode:16s} MAE = {mae:.3f}")

wide.to_csv(CLEAN_DAILY, index=False)

print("\nShape:", wide.shape)
print("Date range:", wide["Date"].min().date(), "to", wide["Date"].max().date())
print("Congestion pricing days with CRZ data:", wide["crz_entries"].notna().sum())
print("\nLatest rows:")
print(wide[["Date", "subway", "subway_pct_prepandemic", "crz_entries", "cbd_entries"]].tail(5).to_string(index=False))
