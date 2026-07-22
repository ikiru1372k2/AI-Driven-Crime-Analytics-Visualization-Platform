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


def test_overview_shows_only_seed_entities(planted):
    """The default (no focus) is the overview: the seed case + its own entities,
    with NO associated cases yet — those are revealed by expanding an entity."""
    seed_case = str(planted["identity_fragment"]["records"][0]["case_id"])
    ov = find_associations(seed_case)
    case_nodes = {n["entity_ref_id"] for n in ov["nodes"] if n["node_type"] == "CASE"}
    assert case_nodes == {seed_case}, "overview must not pre-expand related cases"
    # the seed's entities are present and advertise how many cases they'd reveal
    assert any(n["node_type"] == "POLICE_STATION" for n in ov["nodes"])
    assert ov["total_related"] > 0 and any(v > 0 for v in ov["expandable"].values())


def test_expand_accused_links_same_suspect_cases(planted):
    """Expanding the seed's accused reveals the SAME person's other cases."""
    frag = planted["identity_fragment"]["records"]
    seed_case = str(frag[0]["case_id"])
    other_cases = {str(r["case_id"]) for r in frag[1:]}

    ov = find_associations(seed_case)
    accused = [n for n in ov["nodes"] if n["node_type"] == "ACCUSED_RECORD"]
    focus = max(accused, key=lambda n: ov["expandable"].get(n["node_id"], 0))
    assert ov["expandable"][focus["node_id"]] > 0

    ex = find_associations(seed_case, focus=focus["node_id"], limit=60)
    assert ex["channel"] == "same_suspect"
    case_nodes = {n["entity_ref_id"] for n in ex["nodes"] if n["node_type"] == "CASE"}
    assert other_cases <= case_nodes, f"missing same-suspect cases: {other_cases - case_nodes}"
    si = [e for e in ex["edges"] if e["relationship_type"] == "SAME_IDENTITY"]
    assert si and all(e["classification"] == "POTENTIAL_ASSOCIATION" for e in si)


def test_every_edge_cites_evidence(planted):
    ov = find_associations(str(planted["identity_fragment"]["records"][0]["case_id"]))
    assert ov["edges"]
    assert all(isinstance(e["evidence_case_id"], int) for e in ov["edges"])


def test_filter_narrows_results(planted):
    """Filters are orthogonal: an impossible district drops the related universe to 0."""
    seed = str(planted["identity_fragment"]["records"][0]["case_id"])
    wide = find_associations(seed)
    narrow = find_associations(seed, district_id=999999)  # no such district
    assert narrow["total_related"] < wide["total_related"]
    assert narrow["total_related"] == 0
    assert all(v == 0 for v in narrow["expandable"].values())


def test_unknown_seed_is_empty(planted):
    res = find_associations("999999")
    assert res["seed"] is None
    assert res["association_count"] == 0 and res["nodes"] == []


def test_seed_exposes_ids_and_primary_accused_profile(planted):
    """The overview seed carries the attribute ids + primary-accused profile the
    web client pre-applies as filters when expanding an entity."""
    seed_case = str(planted["identity_fragment"]["records"][0]["case_id"])
    seed = find_associations(seed_case)["seed"]
    # attribute ids are present and non-empty (used to pre-fill crime/district)
    for key in ("subhead_id", "district_id", "station_id"):
        assert seed[key], f"seed missing {key}"
    # the primary-accused profile keys exist (values may be None if unknown)
    for key in ("accused_name", "accused_age", "accused_gender"):
        assert key in seed
    # the seed case has a planted accused, so its profile is populated
    assert seed["accused_name"]


def test_overview_counts_match_default_expansion(planted):
    """A node's overview `expandable` hint must equal what expanding it actually
    returns under the client's default similar-profile pre-filter — so hover
    badges don't over-promise. Here: the crime-sub-head node."""
    seed_case = str(planted["identity_fragment"]["records"][0]["case_id"])
    ov = find_associations(seed_case)
    seed = ov["seed"]
    sub_node = next(n for n in ov["nodes"] if n["node_type"] == "CRIME_SUBHEAD")
    hint = ov["expandable"][sub_node["node_id"]]

    # rebuild the client's default pre-filter for a crime-sub-head expansion:
    # its own attribute (crime type) is dropped; district + suspect profile pinned
    prof = {"district_id": seed["district_id"]}
    if seed["accused_gender"]:
        prof["gender"] = seed["accused_gender"]
    if seed["accused_age"] is not None:
        prof["age_min"] = max(0, seed["accused_age"] - 5)
        prof["age_max"] = min(120, seed["accused_age"] + 5)
    if seed["accused_name"]:
        prof["name_contains"] = seed["accused_name"].split()[0]

    ex = find_associations(seed_case, focus=sub_node["node_id"], limit=10_000, **prof)
    assert ex["total_matches"] == hint, (
        f"overview hint {hint} != expansion total {ex['total_matches']}"
    )
