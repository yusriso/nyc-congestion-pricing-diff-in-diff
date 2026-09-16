"""
Build a station-level geospatial dataset:
- Station monthly ridership (with lat/long already included)
- Joined against MTA Subway Stations and Complexes for CBD (Congestion
  Relief Zone) flag and ADA status
- Aggregated into: latest-month snapshot + pre/post congestion pricing
  comparison per station

Output: station_geo.csv
"""
import pandas as pd

from config import RAW_STATION_RIDERSHIP, RAW_STATIONS, STATION_SNAPSHOT, STATION_COMPARISON

# --- Load station-level monthly ridership ---
rid = pd.read_csv(RAW_STATION_RIDERSHIP)
rid["month"] = pd.to_datetime(rid["month"], format="%m/%d/%Y")
rid = rid.rename(columns={"station_complex_id": "complex_id"})

# --- Load station/complex reference data (for CBD flag + ADA status) ---
stations = pd.read_csv(RAW_STATIONS)
stations = stations.rename(columns={
    "Complex ID": "complex_id",
    "CBD": "in_cbd",
    "ADA": "ada_accessible",
    "Display Name": "display_name",
})
stations_small = stations[["complex_id", "in_cbd", "ada_accessible", "display_name"]].drop_duplicates("complex_id")

# --- Merge ---
rid = rid.merge(stations_small, on="complex_id", how="left")

CONGESTION_PRICING_START = pd.Timestamp("2025-01-05")
rid["congestion_pricing_active"] = rid["month"] >= CONGESTION_PRICING_START

# --- Latest month snapshot (for the main map) ---
latest_month = rid["month"].max()
snapshot = rid[rid["month"] == latest_month].copy()
snapshot = snapshot[[
    "complex_id", "station_complex", "display_name", "borough",
    "latitude", "longitude", "ridership", "transfers", "in_cbd", "ada_accessible",
]]

# --- Pre/post congestion pricing comparison per station ---
# Use a symmetric window so the comparison isn't skewed by data availability:
# 12 months before Jan 5, 2025 vs 12 months after (through the most recent
# full month in the data).
pre_start = CONGESTION_PRICING_START - pd.DateOffset(months=12)
pre_mask = (rid["month"] >= pre_start) & (rid["month"] < CONGESTION_PRICING_START)
post_mask = rid["month"] >= CONGESTION_PRICING_START

pre = rid[pre_mask].groupby("complex_id")["ridership"].mean().rename("avg_monthly_ridership_pre")
post = rid[post_mask].groupby("complex_id")["ridership"].mean().rename("avg_monthly_ridership_post")

comparison = pd.concat([pre, post], axis=1).reset_index()
comparison["pct_change"] = (
    (comparison["avg_monthly_ridership_post"] - comparison["avg_monthly_ridership_pre"])
    / comparison["avg_monthly_ridership_pre"]
) * 100

# Attach station metadata to the comparison table
station_meta = rid[["complex_id", "station_complex", "display_name", "borough",
                     "latitude", "longitude", "in_cbd"]].drop_duplicates("complex_id")
comparison = comparison.merge(station_meta, on="complex_id", how="left")

snapshot.to_csv(STATION_SNAPSHOT, index=False)
comparison.to_csv(STATION_COMPARISON, index=False)

print("Latest month in data:", latest_month.date())
print("Snapshot shape:", snapshot.shape)
print("Comparison shape:", comparison.shape)
print("\nCBD stations:", comparison["in_cbd"].sum(), "/ Non-CBD:", (~comparison["in_cbd"].astype(bool)).sum())
print("\nAvg % change, CBD stations:", comparison.loc[comparison["in_cbd"] == True, "pct_change"].mean().round(1))
print("Avg % change, non-CBD stations:", comparison.loc[comparison["in_cbd"] == False, "pct_change"].mean().round(1))
print("\nSample:")
print(comparison.head())
