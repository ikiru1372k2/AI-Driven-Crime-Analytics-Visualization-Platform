"""District risk features — the SINGLE source of the model's feature contract.

Both the live engine (serving) and the training-data export (offline) build
their rows here, so the columns a district is scored on are byte-for-byte the
columns the QuickML model was trained on. If a feature changes, it changes for
both at once — there is no second definition to drift.

Every feature is derived only from case *counts* in fixed-length windows, so a
row is well-defined for any point in history (needed to build training rows) and
needs no lookup-table encodings we can't guarantee are stable.

Windows count back from the latest case: window 0 is the most recent
``window_days`` days, window 1 the ``window_days`` before that, and so on.
A feature row observed at "recent = window k" predicts the count of window k-1
(the next, more-recent window); at serve time k=0 and we predict the future
window that has not happened yet.

Data is SYNTHETIC (ADR-011); nothing here reads the generator's answer key.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from kavach.api import data

#: The model's input columns, in a fixed order. MUST match the training CSV.
FEATURE_COLUMNS = [
    "recent_count",   # cases in the most recent window
    "prior_count",    # cases in the window before that
    "prior2_count",   # cases two windows back
    "velocity",       # recent / max(prior, 1) — momentum, always defined
    "rolling_mean_3",  # mean of the last three windows
    "trend_slope",    # (recent - prior2) / 2 — direction over three windows
    "month",          # calendar month (1-12) of the TARGET window (seasonality)
]
#: The value the model predicts: the next window's case count.
TARGET_COLUMN = "target_next_count"


def _district_window_counts(
    window_days: int,
) -> tuple[dict[tuple[str, str], np.ndarray], pd.Timestamp, int]:
    """Per-district case counts by window index (0 = most recent).

    Returns ``({(district_id, district_name): counts_array}, latest, max_window)``
    where ``counts_array[k]`` is the number of cases in window k.
    """
    df = data.enriched_cases()
    df = df[df["registered_date"].notna()]
    if df.empty:
        return {}, pd.Timestamp.now().normalize(), 0

    latest = df["registered_date"].max().normalize()
    days_ago = (latest - df["registered_date"].dt.normalize()).dt.days
    win = (days_ago // window_days).astype(int)
    max_window = int(win.max())

    counts: dict[tuple[str, str], np.ndarray] = {}
    tmp = df.assign(_win=win)
    for (did, dname), grp in tmp.groupby(["district_id", "district_name"]):
        arr = np.zeros(max_window + 1, dtype=int)
        vc = grp["_win"].value_counts()
        for k, n in vc.items():
            arr[int(k)] = int(n)
        counts[(did, dname)] = arr
    return counts, latest, max_window


def _row_at(counts: np.ndarray, k: int, target_month: int) -> dict:
    """Feature row treating window ``k`` as 'recent' (predicting window k-1)."""
    c0 = int(counts[k])
    c1 = int(counts[k + 1]) if k + 1 < len(counts) else 0
    c2 = int(counts[k + 2]) if k + 2 < len(counts) else 0
    return {
        "recent_count": c0,
        "prior_count": c1,
        "prior2_count": c2,
        "velocity": round(c0 / max(c1, 1), 3),
        "rolling_mean_3": round((c0 + c1 + c2) / 3, 3),
        "trend_slope": round((c0 - c2) / 2, 3),
        "month": target_month,
    }


def serving_rows(window_days: int = 30) -> list[dict]:
    """Current feature row per district, for predicting the NEXT window.

    Each dict carries the FEATURE_COLUMNS plus ``district_id``/``district_name``
    (identifiers, not fed to the model) — the caller strips the ids before
    calling QuickML.
    """
    counts, latest, _ = _district_window_counts(window_days)
    target_month = int((latest + pd.Timedelta(days=window_days)).month)
    rows: list[dict] = []
    for (did, dname), arr in sorted(counts.items(), key=lambda kv: kv[0][0]):
        row = _row_at(arr, 0, target_month)
        row["district_id"] = did
        row["district_name"] = dname
        row["active_windows"] = int((arr > 0).sum())
        rows.append(row)
    return rows


def training_rows(window_days: int = 30) -> list[dict]:
    """Historical (features -> next-window count) rows for the QuickML CSV.

    Slides the window back through history: for each anchor window k we observe
    windows k, k+1, k+2 and label the row with the count of window k-1.
    """
    counts, latest, max_window = _district_window_counts(window_days)
    rows: list[dict] = []
    for (did, dname), arr in sorted(counts.items(), key=lambda kv: kv[0][0]):
        # need target (k-1 >= 0) and prior2 (k+2 <= max_window)
        for k in range(1, max_window - 1):
            target_end = latest - pd.Timedelta(days=(k - 1) * window_days)
            row = _row_at(arr, k, int(target_end.month))
            row[TARGET_COLUMN] = int(arr[k - 1])
            row["district_id"] = did
            row["district_name"] = dname
            rows.append(row)
    return rows
