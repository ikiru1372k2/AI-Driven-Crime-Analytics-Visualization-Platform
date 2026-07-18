"""Trend detection validation (#35): spike, stability, sparse, sensitivity.

CI ships no committed dataset, so this generates a fresh synthetic dataset into
a temp dir, points the data layer at it, and checks the engine DISCOVERS the
planted robbery spike at Peenya. The planted answer key is read *here* only to
assert detection — the engine never sees it (ADR-011).
"""

import json
import os
from pathlib import Path

import pytest

from kavach.analytics.trends import detect_trends
from kavach.api import data
from kavach.datagen.generator import generate_dataset

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    """Generate a dataset, expose it to the data layer, return the answer key."""
    out = tmp_path_factory.mktemp("trend_synth")
    generate_dataset(out, MANIFEST, seed=20260714, background_cases=800)
    prev = os.environ.get("KAVACH_DATA_DIR")
    os.environ["KAVACH_DATA_DIR"] = str(out)
    data.enriched_cases.cache_clear()
    answer = json.loads((out / "ground_truth.json").read_text())["trend_spike"]
    yield answer
    if prev is None:
        os.environ.pop("KAVACH_DATA_DIR", None)
    else:
        os.environ["KAVACH_DATA_DIR"] = prev
    data.enriched_cases.cache_clear()


def _find(alerts, unit_id, sub_head_id):
    return next(
        (a for a in alerts
         if a["station_id"] == str(unit_id) and a["subhead_id"] == str(sub_head_id)),
        None,
    )


def test_detects_planted_spike(planted):
    res = detect_trends(level="station")
    alert = _find(res["alerts"], planted["unit_id"], planted["sub_head_id"])
    assert alert is not None, "planted robbery spike at Peenya was not detected"
    assert alert["severity"] == "critical"
    assert alert["z_score"] >= 4
    # the recent window sits well above the robust baseline — that IS the spike
    assert alert["recent_weekly"] > alert["baseline_weekly_median"]


def test_spike_is_top_ranked(planted):
    res = detect_trends(level="station")
    assert res["alert_count"] >= 1
    top = res["alerts"][0]
    assert top["station_id"] == str(planted["unit_id"])
    assert top["subhead_id"] == str(planted["sub_head_id"])


def test_stability_few_false_positives(planted):
    # stationary background series should not trip a high threshold en masse
    res = detect_trends(level="station", min_z=3.5)
    assert res["alert_count"] <= 5


def test_sensitivity_threshold_suppresses(planted):
    # a threshold above the spike's z removes every alert
    res = detect_trends(level="station", min_z=100)
    assert res["alert_count"] == 0


def test_sparse_series_suppressed(planted):
    # requiring more recent cases than any series holds -> nothing alerts
    res = detect_trends(level="station", min_recent=100_000)
    assert res["alert_count"] == 0
