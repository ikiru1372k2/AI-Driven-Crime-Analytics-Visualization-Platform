"""Emerging-trend detection (EPIC-TREND, issues #33/#34).

For each crime series (a station x crime-sub-head pair, or a whole sub-head) we
build weekly counts aligned to the latest case, take a *robust* baseline over
the trailing weeks (median + MAD, so a single noisy week can't move it), and
score the recent window with a modified z-score. Series whose recent volume
deviates strongly become ranked alerts, each carrying its own evidence: the
baseline, the deviation, the weekly series for a sparkline, and sample cases.

Robust statistics (median/MAD) are used deliberately over mean/std: crime
counts are low and bursty, and the mean is exactly what a spike distorts.

Input data is SYNTHETIC (ADR-011). This module discovers patterns from the
data alone; it never reads the generator's planted answer key.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from kavach.api import data

#: Provenance identity of this engine (PROV-002 envelope, PROV-001 runs).
METHOD_NAME = "robust_weekly_modified_z"
METHOD_VERSION = "1.0.0"

#: 0.6745 = 0.75 quantile of the normal; scales MAD to a std-equivalent so the
#: modified z-score is comparable to an ordinary z-score.
_MAD_TO_SIGMA = 1.4826
#: floor on the robust spread (cases/week). Weekly counts are integers, so a
#: near-constant low baseline would otherwise make z explode on any wobble.
_SIGMA_FLOOR = 1.0

#: z-score cut points → severity (aligned to the status palette good→critical).
_SEVERITY = [(5.0, "critical"), (3.5, "serious"), (2.5, "warning")]


def _severity(z: float) -> str | None:
    for threshold, label in _SEVERITY:
        if z >= threshold:
            return label
    return None


def detect_trends(
    *,
    level: str = "station",
    subhead_id: int | None = None,
    district_id: int | None = None,
    baseline_weeks: int = 8,
    recent_weeks: int = 2,
    min_z: float = 2.5,
    min_recent: int = 5,
) -> dict:
    """Rank emerging crime trends by robust deviation from baseline.

    Args:
        level: "station" scores each police-station x crime-sub-head series
            (actionable "robbery is spiking at Peenya"); "subhead" scores each
            crime-sub-head statewide.
        subhead_id: restrict to one crime sub-head.
        district_id: restrict to one district.
        baseline_weeks: trailing weeks used for the robust baseline.
        recent_weeks: most-recent weeks scored against the baseline.
        min_z: modified z-score needed to raise an alert.
        min_recent: minimum recent-window case count (suppresses tiny series).
    """
    df = data.enriched_cases()
    df = df[df["registered_date"].notna()].copy()
    if subhead_id is not None:
        df = df[df["subhead_id"] == str(subhead_id)]
    if district_id is not None:
        df = df[df["district_id"] == str(district_id)]

    params = {
        "level": level, "subhead_id": subhead_id, "district_id": district_id,
        "baseline_weeks": baseline_weeks, "recent_weeks": recent_weeks,
        "min_z": min_z, "min_recent": min_recent,
    }
    horizon = recent_weeks + baseline_weeks
    if df.empty:
        return {"synthetic": True, "params": params, "alert_count": 0, "alerts": []}

    # weekly buckets counting back from the latest case: week 0 = most recent 7d
    latest = df["registered_date"].max().normalize()
    days_ago = (latest - df["registered_date"].dt.normalize()).dt.days
    df["_week"] = days_ago // 7
    df = df[df["_week"] < horizon]
    if df.empty:
        return {"synthetic": True, "params": params, "alert_count": 0, "alerts": []}

    if level == "subhead":
        keys = ["subhead_id"]
    else:
        keys = ["station_id", "subhead_id"]

    alerts = []
    for _key, series in df.groupby(keys):
        weekly = series.groupby("_week").size()
        counts = np.array([int(weekly.get(w, 0)) for w in range(horizon)])  # w0=newest
        recent = counts[:recent_weeks]
        baseline = counts[recent_weeks:]
        recent_total = int(recent.sum())
        if recent_total < min_recent:
            continue

        recent_weekly = recent_total / recent_weeks
        median = float(np.median(baseline))
        mad = float(np.median(np.abs(baseline - median)))
        sigma = max(mad * _MAD_TO_SIGMA, _SIGMA_FLOOR)
        z = round((recent_weekly - median) / sigma, 2)
        if z < min_z:
            continue

        row = series.iloc[0]
        pct = None if median == 0 else round((recent_weekly - median) / median * 100, 0)
        recent_cases = series[series["_week"] < recent_weeks]
        alerts.append({
            "level": level,
            "subhead_id": row["subhead_id"],
            "subhead_name": row["subhead_name"],
            "station_id": None if level == "subhead" else row["station_id"],
            "station_name": None if level == "subhead" else row["station_name"],
            "district_name": None if level == "subhead" else row["district_name"],
            "z_score": z,
            "severity": _severity(z),
            "direction": "up",
            "recent_count": recent_total,
            "recent_weekly": round(recent_weekly, 1),
            "baseline_weekly_median": round(median, 1),
            "baseline_mad": round(mad, 2),
            "pct_change": pct,
            "window": {
                "from": (latest - pd.Timedelta(weeks=recent_weeks) + pd.Timedelta(days=1))
                .strftime("%Y-%m-%d"),
                "to": latest.strftime("%Y-%m-%d"),
            },
            # oldest -> newest, for a left-to-right sparkline
            "weekly_series": counts[::-1].tolist(),
            "sample_case_ids": recent_cases["CaseMasterID"].head(10).tolist(),
        })

    alerts.sort(key=lambda a: a["z_score"], reverse=True)
    for rank, a in enumerate(alerts, 1):
        a["rank"] = rank

    return {
        "synthetic": True,
        "params": params,
        "alert_count": len(alerts),
        "alerts": alerts,
    }
