"""
Single place for file paths. Every script imports from here, so moving
the project or renaming a download means editing one file.

Layout:
    project/
        data/raw/         original CSVs from data.ny.gov (not committed if large)
        data/processed/   outputs of the cleaning scripts (committed)
        app.py, clean_data.py, build_geo_data.py, did_analysis.py, config.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Raw downloads (rename here if your download has a different filename)
RAW_DAILY = RAW_DIR / "MTA_Daily_Ridership_and_Traffic__Beginning_2020.csv"
RAW_LEGACY_DAILY = RAW_DIR / "MTA_Daily_Ridership_Data__2020_-_2025.csv"
RAW_STATION_RIDERSHIP = RAW_DIR / "MTA_Subway_Station_Monthly_Ridership__Beginning_February_2017.csv"
RAW_STATIONS = RAW_DIR / "MTA_Subway_Stations_and_Complexes.csv"

# Processed outputs
CLEAN_DAILY = PROCESSED_DIR / "clean_mta_daily.csv"
STATION_SNAPSHOT = PROCESSED_DIR / "station_snapshot.csv"
STATION_COMPARISON = PROCESSED_DIR / "station_congestion_comparison.csv"
DID_RESULTS = PROCESSED_DIR / "did_results.json"
DID_EVENT_STUDY = PROCESSED_DIR / "did_event_study.csv"
