"""Hotspot analytics validation suite (HOT-004, #31).

Proves the DBSCAN hotspot engine against DATA-001 ground truth: known-cluster
recovery (recall / impostor rate), noise control (no fabricated clusters),
cyclic-midnight temporal handling, coordinate-exclusion accounting, and eps
parameter stability. Runs hermetically — a fresh dataset is generated into a
temp dir (CI ships no data) and the data layer is pointed at it.

The planted answer key is read *here* only to score detection; the engine
discovers clusters from coordinates alone and never sees it (ADR-011).

Out of scope: a dedicated spatiotemporal *clustering* mode (23:59/00:01
co-cluster fixtures). The current engine clusters spatially and reports a
cyclic time-of-day profile per cluster; the midnight test below validates that
cyclic profile rather than spatiotemporal linkage.
"""

import json
import os
from pathlib import Path

import pytest

from kavach.analytics.hotspot import detect_hotspots
from kavach.api import data
from kavach.datagen.generator import generate_dataset

ROOT = Path(__file__).resolve().parents[4]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"

# match the validated demo parameters
EPS_M = 350.0
MIN_SAMPLES = 8
DAYS = 90


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    out = tmp_path_factory.mktemp("hotspot_synth")
    generate_dataset(out, MANIFEST, seed=20260714, background_cases=800)
    prev = os.environ.get("KAVACH_DATA_DIR")
    os.environ["KAVACH_DATA_DIR"] = str(out)
    data.enriched_cases.cache_clear()
    gt = json.loads((out / "ground_truth.json").read_text())
    yield gt
    if prev is None:
        os.environ.pop("KAVACH_DATA_DIR", None)
    else:
        os.environ["KAVACH_DATA_DIR"] = prev
    data.enriched_cases.cache_clear()


def _planted_ids(gt) -> set[str]:
    return {str(i) for i in gt["hotspot"]["case_ids"]}


def _geolocated_ids() -> set[str]:
    df = data.enriched_cases()
    df = df[df["latitude"].notna() & df["longitude"].notna()]
    return set(df["CaseMasterID"])


def _best_cluster(res, planted_ids):
    """The detected cluster overlapping the planted hotspot the most."""
    return max(
        res["hotspots"],
        key=lambda h: len(planted_ids & set(h["case_ids"])),
        default=None,
    )


def test_ground_truth_cluster_recovered(planted):
    """≥90% member recall of the planted hotspot, ≤10% impostor rate."""
    subhead = planted["hotspot"]["sub_head_id"]
    res = detect_hotspots(subhead_id=subhead, days=DAYS, eps_m=EPS_M, min_samples=MIN_SAMPLES)
    planted_ids = _planted_ids(planted)
    planted_geo = planted_ids & _geolocated_ids()  # the engine only sees geolocated cases

    cluster = _best_cluster(res, planted_ids)
    assert cluster is not None, "no cluster overlapping the planted hotspot"
    members = set(cluster["case_ids"])

    recall = len(members & planted_geo) / len(planted_geo)
    impostor = len(members - planted_ids) / len(members)
    assert recall >= 0.90, f"recall {recall:.3f} < 0.90"
    assert impostor <= 0.10, f"impostor rate {impostor:.3f} > 0.10"


def test_cluster_located_at_planted_site(planted):
    subhead = planted["hotspot"]["sub_head_id"]
    res = detect_hotspots(subhead_id=subhead, days=DAYS, eps_m=EPS_M, min_samples=MIN_SAMPLES)
    cluster = _best_cluster(res, _planted_ids(planted))
    # centroid within a few hundred metres of the planted centre (rough degree check)
    assert abs(cluster["center"]["lat"] - planted["hotspot"]["center_lat"]) < 0.02
    assert abs(cluster["center"]["lon"] - planted["hotspot"]["center_lon"]) < 0.02


def test_no_false_clusters_in_control(planted):
    """Crime types with no planted concentration yield no clusters, and an
    unreachably high min_samples never fabricates one."""
    hotspot_subhead = planted["hotspot"]["sub_head_id"]
    df = data.enriched_cases()
    others = [int(s) for s in df["subhead_id"].dropna().unique() if int(s) != hotspot_subhead]
    for sid in others:
        res = detect_hotspots(subhead_id=sid, days=DAYS, eps_m=EPS_M, min_samples=MIN_SAMPLES)
        assert res["cluster_count"] == 0, f"unexpected cluster for control subhead {sid}"
    assert detect_hotspots(days=DAYS, eps_m=EPS_M, min_samples=10_000)["cluster_count"] == 0


def test_cyclic_midnight_handling(planted):
    """The planted 21:00–02:00 hotspot reads as night, with the histogram
    populated on both sides of midnight (cyclic handling, not truncated)."""
    subhead = planted["hotspot"]["sub_head_id"]
    res = detect_hotspots(subhead_id=subhead, days=DAYS, eps_m=EPS_M, min_samples=MIN_SAMPLES)
    cluster = _best_cluster(res, _planted_ids(planted))
    assert cluster["night_share"] >= 0.80
    hist = cluster["hour_histogram"]
    assert hist[23] > 0 and (hist[0] > 0 or hist[1] > 0), "midnight wrap not counted"


def test_exclusion_accounting_matches_ground_truth(planted):
    """Geolocated count equals total minus the documented missing-coord cases."""
    dq = planted["data_quality"]
    df = data.enriched_cases()
    geolocated = int((df["latitude"].notna() & df["longitude"].notna()).sum())
    assert len(df) == dq["total_cases"]
    assert len(df) - geolocated == dq["missing_coordinate_cases"]


def test_eps_stability(planted):
    """±10% eps retains ≥80% of ground-truth membership."""
    subhead = planted["hotspot"]["sub_head_id"]
    planted_ids = _planted_ids(planted)
    planted_geo = planted_ids & _geolocated_ids()
    for eps in (EPS_M * 0.9, EPS_M, EPS_M * 1.1):
        res = detect_hotspots(subhead_id=subhead, days=DAYS, eps_m=eps, min_samples=MIN_SAMPLES)
        cluster = _best_cluster(res, planted_ids)
        recall = len(set(cluster["case_ids"]) & planted_geo) / len(planted_geo)
        assert recall >= 0.80, f"eps={eps:.0f} recall {recall:.3f} < 0.80"
