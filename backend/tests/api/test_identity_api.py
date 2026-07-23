"""Contract tests for the redesigned Identities tab endpoints.

``/api/accused/ranked`` (paged ranked list) and ``/api/persons/similar``
(on-demand single-person search) — both attribute-only (ADR-003) and cheap
(never the O(n^2) resolve_identities path).
"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kavach.api import data
from kavach.api.main import app
from kavach.datagen.generator import generate_dataset
from tests.conftest import install_test_auth, uninstall_test_auth

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"


def _clear():
    for name in ("enriched_cases", "accused_records", "victim_records",
                 "_person_case_index", "ranked_accused"):
        getattr(data, name).cache_clear()


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    out = tmp_path_factory.mktemp("identity_api_synth")
    generate_dataset(out, MANIFEST, seed=20260714, background_cases=400)
    prev = os.environ.get("KAVACH_DATA_DIR")
    os.environ["KAVACH_DATA_DIR"] = str(out)
    _clear()
    headers = install_test_auth()
    with TestClient(app, headers=headers) as c:
        yield c
    uninstall_test_auth()
    if prev is None:
        os.environ.pop("KAVACH_DATA_DIR", None)
    else:
        os.environ["KAVACH_DATA_DIR"] = prev
    _clear()


def test_ranked_is_paged_and_ordered(client):
    r = client.get("/api/accused/ranked", params={"limit": 15, "offset": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 15 and body["offset"] == 0
    assert body["total"] >= body["returned"]
    assert len(body["accused"]) == body["returned"] <= 15
    counts = [p["case_count"] for p in body["accused"]]
    assert counts == sorted(counts, reverse=True)
    # second page continues the descending order (never exceeds the first page's tail)
    r2 = client.get("/api/accused/ranked", params={"limit": 15, "offset": 15})
    if r2.json()["accused"]:
        assert r2.json()["accused"][0]["case_count"] <= counts[-1]


def test_similar_search_by_name(client):
    subject = client.get("/api/accused/ranked").json()["accused"][0]
    r = client.get("/api/persons/similar", params={"name": subject["name"]})
    assert r.status_code == 200
    body = r.json()
    assert body["query"]["name"] == subject["name"]
    assert body["match_count"] == len(body["matches"]) >= 1
    top = body["matches"][0]
    assert {"name", "age", "gender", "case_count", "confidence", "contributing"} <= set(top)


def test_similar_sex_filter(client):
    subject = client.get("/api/accused/ranked").json()["accused"][0]
    other = "F" if subject["gender"] != "F" else "M"
    r = client.get(
        "/api/persons/similar",
        params={"name": subject["name"], "age": subject["age"], "sex": other},
    )
    assert r.status_code == 200
    assert all(m["gender"] == other for m in r.json()["matches"])


def test_similar_name_only_is_partial(client):
    """A name-only query is the top search box: a name FRAGMENT still matches."""
    subject = client.get("/api/accused/ranked").json()["accused"][0]
    token = next((t for t in subject["name"].split() if len(t) >= 4), subject["name"])
    frag = token[:3]
    body = client.get("/api/persons/similar", params={"name": frag}).json()
    assert body["match_count"] >= 1
    assert any(m["name"] == subject["name"] for m in body["matches"])


def test_similar_requires_a_name(client):
    assert client.get("/api/persons/similar").status_code == 422
