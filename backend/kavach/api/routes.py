"""Analytics API routes (LOCAL synthetic-data path).

Phase 1: data access (/meta, /cases). Phase 2 adds /hotspots.
All responses are derived from SYNTHETIC data (ADR-011).
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from kavach.analytics.hotspot import detect_hotspots
from kavach.api import data

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/meta")
def get_meta() -> dict:
    """Lookups + dataset summary for filters, map centering and the demo banner."""
    return data.meta()


@router.get("/cases")
def get_cases(
    subhead_id: int | None = Query(default=None, description="filter by crime sub-head"),
    district_id: int | None = Query(default=None),
    station_id: int | None = Query(default=None),
    date_from: str | None = Query(default=None, description="YYYY-MM-DD (inclusive)"),
    date_to: str | None = Query(default=None, description="YYYY-MM-DD (inclusive)"),
    with_coords: bool = Query(default=True, description="only geolocated cases"),
    limit: int | None = Query(default=None, ge=1, le=10000),
) -> dict:
    """Filtered case rows for the map / list views."""
    rows = data.case_records(
        subhead_id=subhead_id,
        district_id=district_id,
        station_id=station_id,
        date_from=date_from,
        date_to=date_to,
        with_coords=with_coords,
        limit=limit,
    )
    return {"synthetic": True, "count": len(rows), "cases": rows}


@router.get("/hotspots")
def get_hotspots(
    subhead_id: int | None = Query(default=None, description="crime sub-head, e.g. 71=Robbery"),
    district_id: int | None = Query(default=None),
    days: int | None = Query(default=None, description="recency window: days back from latest"),
    eps_m: float = Query(default=400.0, gt=0, le=5000, description="cluster radius in metres"),
    min_samples: int = Query(default=8, ge=2, le=100),
) -> dict:
    """Spatial crime hotspots via DBSCAN (haversine), ranked by case count."""
    return detect_hotspots(
        subhead_id=subhead_id,
        district_id=district_id,
        days=days,
        eps_m=eps_m,
        min_samples=min_samples,
    )
