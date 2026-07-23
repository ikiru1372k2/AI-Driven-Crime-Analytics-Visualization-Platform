#!/usr/bin/env python3
"""Export the QuickML training table for the area-risk forecast (FORECAST tab).

The forecast is produced by a trained Zoho QuickML pipeline, not by us. This
script builds the CSV that trains it, using the SAME feature builder the live
engine uses at serve time (``kavach.analytics.risk.features``) — so the columns
the model learns are exactly the columns it is later scored on. There is no
second feature definition to drift.

Each row is one district observed at one point in history: the feature columns
plus ``target_next_count`` (the next window's actual case count, the label).

Usage (from repo root):

    PYTHONPATH=backend backend/.venv/Scripts/python.exe scripts/risk_train_export.py

Then, in the Catalyst console: QuickML -> new pipeline -> upload this CSV ->
target column = target_next_count -> train a regression model -> publish an
endpoint -> copy its endpoint key into KAVACH_QUICKML_RISK_ENDPOINT.

The CSV is deliberately ALL-NUMERIC: only the model's feature columns plus the
target. District identifiers are *not* written — QuickML's pipeline rejects a
training set with any non-numeric column ("Previous stage result contains
non-numeric columns"), and the identifiers are not features anyway. The columns
are:

    recent_count, prior_count, prior2_count, velocity, rolling_mean_3,
    trend_slope, month, target_next_count

All data is SYNTHETIC (ADR-011).
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "risk_train_model.csv"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--window-days", type=int, default=30, help="window / horizon length")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)

    from kavach.analytics.risk import features

    rows = features.training_rows(args.window_days)
    if not rows:
        raise SystemExit("no training rows — generate the dataset first")

    # ALL-NUMERIC training table: feature columns then the target, nothing else.
    # District identifiers are dropped — they are not features, and any
    # non-numeric column makes QuickML's pipeline reject the training set.
    header = [*features.FEATURE_COLUMNS, features.TARGET_COLUMN]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"wrote {len(rows)} rows -> {out}\n"
        f"  target column: {features.TARGET_COLUMN}\n"
        f"  feature columns: {', '.join(features.FEATURE_COLUMNS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
