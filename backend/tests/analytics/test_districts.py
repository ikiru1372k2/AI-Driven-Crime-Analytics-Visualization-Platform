"""District aggregate + velocity checks (supports the choropleth, #61)."""

import os
from pathlib import Path

import pytest

from kavach.api import data
from kavach.datagen.generator import generate_dataset

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    out = tmp_path_factory.mktemp("district_synth")
    generate_dataset(out, MANIFEST, seed=20260714, background_cases=800)
    prev = os.environ.get("KAVACH_DATA_DIR")
    os.environ["KAVACH_DATA_DIR"] = str(out)
    data.enriched_cases.cache_clear()
    yield
    if prev is None:
        os.environ.pop("KAVACH_DATA_DIR", None)
    else:
        os.environ["KAVACH_DATA_DIR"] = prev
    data.enriched_cases.cache_clear()


def test_every_district_reported(dataset):
    stats = data.district_stats()
    df = data.enriched_cases()
    assert {s["district_id"] for s in stats} == set(df["district_id"].dropna().unique())
    assert sum(s["case_count"] for s in stats) == len(df)


def test_counts_and_velocity_are_sane(dataset):
    stats = data.district_stats()
    for s in stats:
        assert s["case_count"] >= s["cases_with_coords"] >= 0
        assert s["recent_count"] >= 0 and s["prior_count"] >= 0
        assert s["velocity"] is None or s["velocity"] >= 0
    # ranked by case_count descending
    assert stats == sorted(stats, key=lambda s: s["case_count"], reverse=True)


def test_bengaluru_leads_volume(dataset):
    # the planted hotspot + spike make Bengaluru City the largest by volume
    stats = data.district_stats()
    assert stats[0]["district_name"] == "Bengaluru City"
