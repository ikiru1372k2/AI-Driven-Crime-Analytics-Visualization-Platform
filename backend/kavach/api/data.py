"""Local synthetic-data access for the analytics API (LOCAL/demo path).

Reads the generated CSVs from ``data/synthetic`` into pandas DataFrames, joins
human-readable lookup names, and caches the result. This is deliberately the
LOCAL adapter — the Catalyst Data Store adapter (CAT-002) will later expose the
same enriched-case shape behind the same functions, so API/analytics code does
not change when persistence moves to Catalyst.

All data is SYNTHETIC (ADR-011). Nothing here reads ground_truth.json.
"""

from __future__ import annotations

import functools
import os
from pathlib import Path

import pandas as pd

#: repo root = backend/kavach/api/data.py -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]


def data_dir() -> Path:
    """Directory holding the generated CSVs (override with KAVACH_DATA_DIR)."""
    return Path(os.environ.get("KAVACH_DATA_DIR", _REPO_ROOT / "data" / "synthetic"))


def _read(name: str) -> pd.DataFrame:
    """Read one source CSV as strings ("" for blanks), preserving raw values."""
    path = data_dir() / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found — generate the dataset first: "
            "PYTHONPATH=backend backend/.venv/Scripts/python.exe scripts/generate_dataset.py"
        )
    return pd.read_csv(path, dtype=str, keep_default_na=False)


@functools.lru_cache(maxsize=1)
def enriched_cases() -> pd.DataFrame:
    """CaseMaster joined with its lookup names, one row per FIR.

    Adds: subhead_name, head_id/head_name, category, gravity, status,
    station_name, district_id/district_name, plus typed lat/lon and dates.
    Cached for the process lifetime (dataset is static for a demo run).
    """
    cases = _read("CaseMaster")
    subheads = _read("CrimeSubHead")[["CrimeSubHeadID", "CrimeHeadID", "CrimeHeadName"]]
    heads = _read("CrimeHead")[["CrimeHeadID", "CrimeGroupName"]]
    units = _read("Unit")[["UnitID", "UnitName", "DistrictID"]]
    districts = _read("District")[["DistrictID", "DistrictName"]]
    categories = _read("CaseCategory")[["CaseCategoryID", "LookupValue"]]
    gravity = _read("GravityOffence")[["GravityOffenceID", "LookupValue"]]
    statuses = _read("CaseStatusMaster")[["CaseStatusID", "CaseStatusName"]]

    df = cases.merge(
        subheads, left_on="CrimeMinorHeadID", right_on="CrimeSubHeadID", how="left"
    ).merge(heads, on="CrimeHeadID", how="left")

    df = df.merge(units, left_on="PoliceStationID", right_on="UnitID", how="left")
    df = df.merge(districts, on="DistrictID", how="left")
    df = df.merge(
        categories, left_on="CaseCategoryID", right_on="CaseCategoryID", how="left"
    )
    df = df.merge(
        gravity, left_on="GravityOffenceID", right_on="GravityOffenceID",
        how="left", suffixes=("", "_grav"),
    )
    df = df.merge(statuses, left_on="CaseStatusID", right_on="CaseStatusID", how="left")

    # typed / renamed convenience columns
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["registered_date"] = pd.to_datetime(df["CrimeRegisteredDate"], errors="coerce")
    df["incident_from"] = pd.to_datetime(df["IncidentFromDate"], errors="coerce")
    df = df.rename(
        columns={
            "CrimeHeadName": "subhead_name",
            "CrimeHeadID": "head_id",
            "CrimeGroupName": "head_name",
            "UnitName": "station_name",
            "DistrictName": "district_name",
            "LookupValue": "category",
            "LookupValue_grav": "gravity",
            "CaseStatusName": "status",
            "CrimeMinorHeadID": "subhead_id",
            "PoliceStationID": "station_id",
            "DistrictID": "district_id",
        }
    )
    return df


#: fields returned to the client for a single case (map-friendly)
_CASE_FIELDS = [
    "CaseMasterID", "CrimeNo", "registered_date", "incident_from",
    "latitude", "longitude", "subhead_id", "subhead_name", "head_id", "head_name",
    "category", "gravity", "status", "station_id", "station_name",
    "district_id", "district_name",
]


def case_records(
    *,
    subhead_id: int | None = None,
    district_id: int | None = None,
    station_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    with_coords: bool = True,
    limit: int | None = None,
) -> list[dict]:
    """Filtered, JSON-ready case rows for the map/list views."""
    df = enriched_cases()
    if with_coords:
        df = df[df["latitude"].notna() & df["longitude"].notna()]
    if subhead_id is not None:
        df = df[df["subhead_id"] == str(subhead_id)]
    if district_id is not None:
        df = df[df["district_id"] == str(district_id)]
    if station_id is not None:
        df = df[df["station_id"] == str(station_id)]
    if date_from:
        df = df[df["registered_date"] >= pd.to_datetime(date_from)]
    if date_to:
        df = df[df["registered_date"] <= pd.to_datetime(date_to)]
    if limit is not None:
        df = df.head(limit)

    out = df[_CASE_FIELDS].copy()
    out["registered_date"] = out["registered_date"].dt.strftime("%Y-%m-%d")
    out["incident_from"] = out["incident_from"].dt.strftime("%Y-%m-%d %H:%M")
    return out.where(out.notna(), None).to_dict(orient="records")


def meta() -> dict:
    """Lookup values + dataset summary for filters, map centering, and banners."""
    df = enriched_cases()
    with_coords = df[df["latitude"].notna() & df["longitude"].notna()]
    subheads = (
        df[["subhead_id", "subhead_name", "head_id", "head_name"]]
        .drop_duplicates()
        .sort_values("subhead_id")
    )
    districts = (
        df[["district_id", "district_name"]].drop_duplicates().sort_values("district_id")
    )
    stations = (
        df[["station_id", "station_name", "district_id"]]
        .drop_duplicates()
        .sort_values("station_id")
    )
    dmin = df["registered_date"].min()
    dmax = df["registered_date"].max()
    center_lat = float(with_coords["latitude"].mean())
    center_lon = float(with_coords["longitude"].mean())
    return {
        "synthetic": True,
        "total_cases": int(len(df)),
        "cases_with_coords": int(len(with_coords)),
        "date_range": {
            "from": None if pd.isna(dmin) else dmin.strftime("%Y-%m-%d"),
            "to": None if pd.isna(dmax) else dmax.strftime("%Y-%m-%d"),
        },
        "map_center": {"lat": center_lat, "lon": center_lon},
        "crime_subheads": subheads.where(subheads.notna(), None).to_dict(orient="records"),
        "districts": districts.where(districts.notna(), None).to_dict(orient="records"),
        "stations": stations.where(stations.notna(), None).to_dict(orient="records"),
        "statuses": sorted(x for x in df["status"].dropna().unique().tolist()),
    }
