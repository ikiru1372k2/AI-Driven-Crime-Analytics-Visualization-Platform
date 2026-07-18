"""Analytics API routes (LOCAL synthetic-data path).

Phase 1: data access (/meta, /cases). Phase 2 adds /hotspots.
All responses are derived from SYNTHETIC data (ADR-011).
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from kavach.analytics.hotspot import detect_hotspots
from kavach.analytics.trends import detect_trends
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


@router.get("/trends")
def get_trends(
    level: str = Query(default="station", pattern="^(station|subhead)$"),
    subhead_id: int | None = Query(default=None),
    district_id: int | None = Query(default=None),
    baseline_weeks: int = Query(default=8, ge=2, le=52),
    recent_weeks: int = Query(default=2, ge=1, le=8),
    min_z: float = Query(default=2.5, ge=0, description="alert threshold (modified z)"),
    min_recent: int = Query(default=5, ge=1, description="min recent-window cases"),
) -> dict:
    """Emerging-trend alerts via robust weekly baselines + modified z-score."""
    return detect_trends(
        level=level,
        subhead_id=subhead_id,
        district_id=district_id,
        baseline_weeks=baseline_weeks,
        recent_weeks=recent_weeks,
        min_z=min_z,
        min_recent=min_recent,
    )


@router.get("/districts")
def get_districts(window_days: int = Query(default=30, ge=7, le=180)) -> dict:
    """Per-district totals + recent-vs-prior case velocity (choropleth source)."""
    return {
        "synthetic": True,
        "window_days": window_days,
        "districts": data.district_stats(window_days),
    }


@router.get("/overview")
def get_overview() -> dict:
    """State intelligence summary: what requires attention now (issue #62).

    Composes the dataset summary with the top emerging trends and the largest
    spatial hotspots, plus an alert-severity tally for the headline.
    """
    m = data.meta()
    trends = detect_trends(level="station")
    hotspots = detect_hotspots(days=90)
    sev_order = {"critical": 0, "serious": 1, "warning": 2}
    tally = {"critical": 0, "serious": 0, "warning": 0}
    for a in trends["alerts"]:
        if a["severity"] in tally:
            tally[a["severity"]] += 1
    return {
        "synthetic": True,
        "total_cases": m["total_cases"],
        "date_range": m["date_range"],
        "map_center": m["map_center"],
        "alert_tally": tally,
        "top_trends": sorted(
            trends["alerts"], key=lambda a: (sev_order.get(a["severity"], 9), -a["z_score"])
        )[:5],
        "top_hotspots": hotspots["hotspots"][:5],
        "hotspot_count": hotspots["cluster_count"],
    }
