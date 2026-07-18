"""Entity resolution validation (#50): ground truth, same-name control, no auto-merge.

Hermetic - generates a dataset into a temp dir (CI ships none). Reads the planted
answer key here only to score detection; the engine discovers identities from
attributes alone (ADR-011) and never joins on PersonID (ADR-003).
"""

import json
import os
from pathlib import Path

import pytest

from kavach.analytics.entity import resolve_identities
from kavach.api import data
from kavach.datagen.generator import generate_dataset

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    out = tmp_path_factory.mktemp("entity_synth")
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


def _cluster_of(result, accused_id):
    for c in result["candidates"]:
        if any(m["accused_id"] == str(accused_id) for m in c["members"]):
            return c
    return None


def test_fragment_records_are_linked(planted):
    """The three fragmented-name records of one person land in one cluster."""
    frag_ids = [str(r["accused_master_id"]) for r in planted["identity_fragment"]["records"]]
    res = resolve_identities()
    clusters = {_cluster_of(res, i)["cluster_id"] for i in frag_ids if _cluster_of(res, i)}
    assert len(clusters) == 1, f"fragment split across clusters: {clusters}"
    cluster = _cluster_of(res, frag_ids[0])
    member_ids = {m["accused_id"] for m in cluster["members"]}
    assert set(frag_ids) <= member_ids  # >=90% recall (all 3 present)


def test_same_name_control_not_merged(planted):
    """Two different people sharing a name (ages far apart) must NOT be merged."""
    a, b = (str(r["accused_master_id"]) for r in planted["same_name_control"]["records"])
    res = resolve_identities()
    ca, cb = _cluster_of(res, a), _cluster_of(res, b)
    together = ca is not None and cb is not None and ca["cluster_id"] == cb["cluster_id"]
    assert not together, "same-name decoy was incorrectly merged"


def test_clusters_are_age_coherent(planted):
    """No cluster chains across an implausible age span (single-link guard)."""
    res = resolve_identities()
    for c in res["candidates"]:
        if c["age_range"]:
            assert c["age_range"][1] - c["age_range"][0] <= 10


def test_nothing_is_auto_merged(planted):
    res = resolve_identities()
    assert all(c["status"] == "pending_review" for c in res["candidates"])


def test_personid_not_used_for_identity(planted):
    """ADR-003: identity is discovered from attributes, never carried by PersonID.

    (The SQL-context PersonID guard is enforced repo-wide in the ER conformance
    suite; here we assert the ER data path never even surfaces the field.)
    """
    assert all("PersonID" not in r for r in data.accused_records())
    res = resolve_identities()
    for c in res["candidates"]:
        for m in c["members"]:
            assert "PersonID" not in m and "person_id" not in m
