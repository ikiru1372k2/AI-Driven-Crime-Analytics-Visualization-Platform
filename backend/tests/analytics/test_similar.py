"""On-demand person search (ranked list + find_similar).

These back the redesigned Identities tab: a cheap ranked list and a single-person
similarity search that must NEVER fall back to the O(n^2) ``resolve_identities``
path (which timed out). Hermetic — generates a dataset into a temp dir and reads
the planted answer key only to locate test subjects; identity is discovered from
attributes alone (ADR-003/ADR-011).
"""

import os
from pathlib import Path

import pytest

from kavach.analytics.entity import engine, find_similar
from kavach.api import data

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"


@pytest.fixture(scope="module")
def synth(tmp_path_factory):
    from kavach.datagen.generator import generate_dataset

    out = tmp_path_factory.mktemp("similar_synth")
    generate_dataset(out, MANIFEST, seed=20260714, background_cases=800)
    prev = os.environ.get("KAVACH_DATA_DIR")
    os.environ["KAVACH_DATA_DIR"] = str(out)
    _clear()
    yield out
    if prev is None:
        os.environ.pop("KAVACH_DATA_DIR", None)
    else:
        os.environ["KAVACH_DATA_DIR"] = prev
    _clear()


def _clear():
    for name in ("enriched_cases", "accused_records", "victim_records",
                 "_person_case_index", "ranked_accused"):
        getattr(data, name).cache_clear()
    engine.resolve_identities.cache_clear()


def _first_accused(synth):
    """A real accused person (name/age/gender) to use as a query subject."""
    return next(r for r in data.accused_records() if r["name"] and r["gender"])


def test_ranked_by_crime_count_desc(synth):
    """Persons come back ordered by number of crimes, most first."""
    people = data.ranked_accused()
    assert people, "expected at least one accused person"
    counts = [p["case_count"] for p in people]
    assert counts == sorted(counts, reverse=True)
    assert all(p["case_count"] >= 1 for p in people)


def test_ranked_has_no_personid(synth):
    """ADR-003: the ranked list is attribute-only, never PersonID."""
    for p in data.ranked_accused():
        assert "PersonID" not in p and "person_id" not in p
        assert set(p) == {"name", "age", "gender", "districts", "case_count"}


def test_find_similar_finds_self_and_kin(synth):
    """A query person matches at least their own record, at top confidence."""
    q = _first_accused(synth)
    matches = find_similar(q["name"], q["age"], q["gender"])
    assert matches, "query person should match themselves"
    assert matches[0]["confidence"] == max(m["confidence"] for m in matches)
    assert any(m["name"] == q["name"] and m["age"] == q["age"] for m in matches)


def test_find_similar_sex_is_a_hard_filter(synth):
    """When sex is given, no opposite-gender person is ever returned."""
    q = _first_accused(synth)
    other = "F" if q["gender"] != "F" else "M"
    matches = find_similar(q["name"], q["age"], other)
    assert all(m["gender"] == other for m in matches)


def test_find_similar_name_only(synth):
    """The top search (name only, no age/sex) still returns matches."""
    q = _first_accused(synth)
    matches = find_similar(q["name"])
    assert matches
    assert all(m["name_sim"] >= 0.5 for m in matches)


def test_find_similar_partial_matches_name_fragment(synth):
    """The top search does PARTIAL matching: a short fragment of a name is a hit."""
    q = _first_accused(synth)
    token = next((t for t in q["name"].split() if len(t) >= 4), q["name"])
    frag = token[:3]  # a 3-letter fragment, like the min the UI enforces
    matches = find_similar(frag, partial=True)
    assert any(m["name"] == q["name"] for m in matches), (frag, q["name"])
    assert all("name matches" in m["contributing"][0] for m in matches)


def test_find_similar_partial_matches_surname_fragment(synth):
    """Partial finds a person by a SURNAME fragment — something the strict,
    given-name-anchored scorer (partial=False) cannot do."""
    q = next(
        (r for r in data.accused_records()
         if r["name"] and r["gender"] and len(r["name"].split()) >= 2),
        None,
    )
    if q is None:
        pytest.skip("no multi-token names in this dataset")
    surname = q["name"].split()[-1]
    if len(surname) < 3:
        pytest.skip("surname too short for a 3-letter fragment")
    frag = surname[:3]
    assert any(m["name"] == q["name"] for m in find_similar(frag, partial=True))


def test_find_similar_never_calls_resolve_identities(synth):
    """The whole point: the search path is O(n) and must not touch the O(n^2)
    ``resolve_identities`` cache — otherwise it would time out like before."""
    engine.resolve_identities.cache_clear()
    q = _first_accused(synth)
    find_similar(q["name"], q["age"], q["gender"])
    find_similar(q["name"])  # name-only path too
    info = engine.resolve_identities.cache_info()
    assert info.misses == 0 and info.hits == 0 and info.currsize == 0
