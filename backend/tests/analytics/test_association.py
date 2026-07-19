"""Association search validation (EPIC-ASSOC).

Hermetic: generates a dataset, points the data layer at it, and checks that
seeding on the planted identity fragment surfaces the SAME suspect's other
cases (SAME_IDENTITY edges) and that orthogonal filters narrow the result.
The engine discovers everything from data; it never reads the answer key.
"""

import json
import os
from pathlib import Path

import pytest

from kavach.analytics.association import engine as assoc_engine
from kavach.analytics.association import find_associations
from kavach.api import data
from kavach.datagen.generator import generate_dataset

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    out = tmp_path_factory.mktemp("assoc_synth")
    generate_dataset(out, MANIFEST, seed=20260714, background_cases=800)
    prev = os.environ.get("KAVACH_DATA_DIR")
    os.environ["KAVACH_DATA_DIR"] = str(out)
    data.enriched_cases.cache_clear()
    assoc_engine._same_suspect_index.cache_clear()
    gt = json.loads((out / "ground_truth.json").read_text())
    yield gt
    if prev is None:
        os.environ.pop("KAVACH_DATA_DIR", None)
    else:
        os.environ["KAVACH_DATA_DIR"] = prev
    data.enriched_cases.cache_clear()
    assoc_engine._same_suspect_index.cache_clear()


def test_same_suspect_links_fragment_cases(planted):
    """Seeding the fragment's first case links to the same person's other cases."""
    frag = planted["identity_fragment"]["records"]
    seed_case = str(frag[0]["case_id"])
    other_cases = {str(r["case_id"]) for r in frag[1:]}

    res = find_associations(seed_case, limit=60)
    assert "same_suspect" in res["channels"]
    # the other fragment cases appear as associated CASE nodes
    case_nodes = {n["entity_ref_id"] for n in res["nodes"] if n["node_type"] == "CASE"}
    assert other_cases <= case_nodes, f"missing same-suspect cases: {other_cases - case_nodes}"
    # and there are SAME_IDENTITY edges (candidate, not auto-confirmed)
    si = [e for e in res["edges"] if e["relationship_type"] == "SAME_IDENTITY"]
    assert si and all(e["classification"] == "POTENTIAL_ASSOCIATION" for e in si)


def test_every_edge_cites_evidence(planted):
    res = find_associations(str(planted["identity_fragment"]["records"][0]["case_id"]))
    assert res["edges"]
    assert all(isinstance(e["evidence_case_id"], int) for e in res["edges"])


def test_filter_narrows_results(planted):
    seed = str(planted["identity_fragment"]["records"][0]["case_id"])
    wide = find_associations(seed, limit=150)
    narrow = find_associations(seed, limit=150, district_id=999999)  # no such district
    assert narrow["association_count"] < wide["association_count"]
    assert narrow["association_count"] == 0


def test_unknown_seed_is_empty(planted):
    res = find_associations("999999")
    assert res["seed"] is None
    assert res["association_count"] == 0 and res["nodes"] == []
