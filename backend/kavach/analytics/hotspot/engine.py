"""Spatiotemporal hotspot detection (EPIC-HOT).

DBSCAN with the haversine metric over geolocated case coordinates, so the
neighbourhood radius (``eps``) is a real-world distance in metres rather than a
degree approximation. Optional recency and crime-type filters let an analyst
ask "where are robberies clustering in the last 90 days?".

Each returned hotspot carries its own evidence — the contributing case IDs, a
crime-type breakdown, and a 24-bin time-of-day histogram — so the map can layer
*time* over *place* and the result is explainable, not a black box.

Input data is SYNTHETIC (ADR-011). This module never reads ground_truth.json;
detection is validated against it separately.
"""

from __future__ import annotations

import math
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

from kavach.api import data

_EARTH_RADIUS_M = 6_371_000.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return _EARTH_RADIUS_M * 2 * math.asin(math.sqrt(a))


def detect_hotspots(
    *,
    subhead_id: int | None = None,
    district_id: int | None = None,
    days: int | None = None,
    eps_m: float = 400.0,
    min_samples: int = 8,
) -> dict:
    """Cluster geolocated cases into spatial hotspots.

    Args:
        subhead_id: restrict to one crime sub-head (e.g. 71 = Robbery).
        district_id: restrict to one district.
        days: only cases registered within this many days of the latest case.
        eps_m: DBSCAN neighbourhood radius, in metres.
        min_samples: minimum cases for a core point (cluster seed).
    """
    df = data.enriched_cases()
    df = df[df["latitude"].notna() & df["longitude"].notna()].copy()

    if subhead_id is not None:
        df = df[df["subhead_id"] == str(subhead_id)]
    if district_id is not None:
        df = df[df["district_id"] == str(district_id)]
    if days is not None and not df.empty:
        latest = df["registered_date"].max()
        df = df[df["registered_date"] >= latest - pd.Timedelta(days=days)]

    params = {
        "subhead_id": subhead_id, "district_id": district_id, "days": days,
        "eps_m": eps_m, "min_samples": min_samples,
    }
    if len(df) < min_samples:
        return {"synthetic": True, "params": params, "cluster_count": 0,
                "clustered_cases": 0, "noise_cases": int(len(df)), "hotspots": []}

    coords = np.radians(df[["latitude", "longitude"]].to_numpy(dtype=float))
    labels = DBSCAN(
        eps=eps_m / _EARTH_RADIUS_M, min_samples=min_samples,
        metric="haversine", algorithm="ball_tree",
    ).fit_predict(coords)
    df = df.assign(_cluster=labels)

    hotspots = []
    for label in sorted(set(labels) - {-1}):
        c = df[df["_cluster"] == label]
        clat = float(c["latitude"].mean())
        clon = float(c["longitude"].mean())
        radius = max(
            _haversine_m(clat, clon, la, lo)
            for la, lo in zip(c["latitude"], c["longitude"])
        )
        hours = pd.to_datetime(c["incident_from"], errors="coerce").dt.hour.dropna()
        hour_hist = [int((hours == h).sum()) for h in range(24)]
        night = int(hours.isin([21, 22, 23, 0, 1, 2]).sum())
        crime_breakdown = Counter(c["subhead_name"].dropna())
        hotspots.append({
            "case_count": int(len(c)),
            "center": {"lat": round(clat, 6), "lon": round(clon, 6)},
            "radius_m": round(radius, 1),
            "top_crime": crime_breakdown.most_common(1)[0][0] if crime_breakdown else None,
            "crime_breakdown": dict(crime_breakdown),
            "district_name": c["district_name"].mode().iat[0] if not c.empty else None,
            "station_name": c["station_name"].mode().iat[0] if not c.empty else None,
            "hour_histogram": hour_hist,
            "night_share": round(night / len(c), 3),
            "sample_case_ids": c["CaseMasterID"].head(10).tolist(),
        })

    hotspots.sort(key=lambda h: h["case_count"], reverse=True)
    for rank, h in enumerate(hotspots, 1):
        h["rank"] = rank

    return {
        "synthetic": True,
        "params": params,
        "cluster_count": len(hotspots),
        "clustered_cases": int((labels != -1).sum()),
        "noise_cases": int((labels == -1).sum()),
        "hotspots": hotspots,
    }
