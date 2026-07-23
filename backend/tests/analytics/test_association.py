"""Association search validation (EPIC-ASSOC).

Hermetic: generates a dataset, points the data layer at it, and checks that
seeding on the planted identity fragment surfaces the SAME suspect's other
cases (SAME_IDENTITY edges) and that orthogonal filters narrow the result.
The engine discovers everything from data; it never reads the answer key.

The overview (no focus) is deliberately TRIVIAL (PERF-001): it lists only the
seed's own entities, each flagged expandable, and computes NO counts and NO
entity resolution. All related-case work happens on expansion.
"""

import json
import os
from pathlib import Path

import pytest

from kavach.analytics.association import engine as assoc_engine
from kavach.analytics.association import find_associations
from kavach.analytics.entity import resolve_identities
from kavach.api import data
from kavach.datagen.generator import generate_dataset

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"


def _clear() -> None:
    data.enriched_cases.cache_clear()
    data.accused_records.cache_clear()
    data.victim_records.cache_clear()
    resolve_identities.cache_clear()
    assoc_engine.cache_clear()


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    out = tmp_path_factory.mktemp("assoc_synth")
    generate_dataset(out, MANIFEST, seed=20260714, background_cases=800)
    prev = os.environ.get("KAVACH_DATA_DIR")
    os.environ["KAVACH_DATA_DIR"] = str(out)
    _clear()
    gt = json.loads((out / "ground_truth.json").read_text())
    yield gt
    if prev is None:
        os.environ.pop("KAVACH_DATA_DIR", None)
    else:
        os.environ["KAVACH_DATA_DIR"] = prev
    _clear()


def test_overview_shows_only_seed_entities(planted):
    """The default (no focus) is the overview: the seed case + its own entities,
    with NO associated cases yet — those are revealed by expanding an entity."""
    seed_case = str(planted["identity_fragment"]["records"][0]["case_id"])
    ov = find_associations(seed_case)
    case_nodes = {n["entity_ref_id"] for n in ov["nodes"] if n["node_type"] == "CASE"}
    assert case_nodes == {seed_case}, "overview must not pre-expand related cases"
    # the seed's entities are present and flagged expandable (no counts computed)
    assert any(n["node_type"] == "POLICE_STATION" for n in ov["nodes"])
    assert ov["expandable"] and all(v for v in ov["expandable"].values())
    # the overview is trivial: it computes no related-case universe
    assert ov["total_related"] == 0


def test_expand_accused_links_same_suspect_cases(planted):
    """Expanding the seed's accused reveals the SAME person's other cases."""
    frag = planted["identity_fragment"]["records"]
    seed_case = str(frag[0]["case_id"])
    other_cases = {str(r["case_id"]) for r in frag[1:]}

    ov = find_associations(seed_case)
    accused = [n for n in ov["nodes"] if n["node_type"] == "ACCUSED_RECORD"]
    assert accused, "seed case has no accused to expand"

    # expand every accused the seed has; the same-suspect cluster must cover the
    # planted fragment's other cases (no overview count to pick the node by).
    found: set[str] = set()
    saw_same_identity = False
    for a in accused:
        ex = find_associations(seed_case, focus=a["node_id"], limit=60)
        assert ex["channel"] == "same_suspect"
        found |= {n["entity_ref_id"] for n in ex["nodes"] if n["node_type"] == "CASE"}
        si = [e for e in ex["edges"] if e["relationship_type"] == "SAME_IDENTITY"]
        if si:
            saw_same_identity = True
            assert all(e["classification"] == "POTENTIAL_ASSOCIATION" for e in si)
    assert other_cases <= found, f"missing same-suspect cases: {other_cases - found}"
    assert saw_same_identity


def test_every_edge_cites_evidence(planted):
    ov = find_associations(str(planted["identity_fragment"]["records"][0]["case_id"]))
    assert ov["edges"]
    assert all(isinstance(e["evidence_case_id"], int) for e in ov["edges"])


def test_filter_narrows_expansion(planted):
    """Filters are applied SERVER-SIDE on an expansion (orthogonal to the View):
    an impossible crime type drops a district expansion's matches to 0."""
    seed = str(planted["identity_fragment"]["records"][0]["case_id"])
    ov = find_associations(seed)
    di = next(n for n in ov["nodes"] if n["node_type"] == "DISTRICT")
    wide = find_associations(seed, focus=di["node_id"], limit=10_000)
    narrow = find_associations(seed, focus=di["node_id"], limit=10_000, subhead_id=999999)
    assert narrow["total_matches"] == 0
    assert narrow["total_matches"] <= wide["total_matches"]


def test_expansion_paginates(planted):
    """An expansion returns one page; offset/limit walk the related cases."""
    seed = str(planted["identity_fragment"]["records"][0]["case_id"])
    ov = find_associations(seed)
    di = next(n for n in ov["nodes"] if n["node_type"] == "DISTRICT")
    page = find_associations(seed, focus=di["node_id"], limit=5, offset=0)
    assert page["association_count"] <= 5
    assert page["association_count"] <= page["total_matches"]
    assert page["offset"] == 0


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
