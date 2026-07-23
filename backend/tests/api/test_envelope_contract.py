"""PROV-002/#25: envelope serializer units + router contract tests.

Contract: every analytics response carries a valid `intelligence` envelope
whose classification is machine-readable and whose label comes from the
centralized string table (i18n-ready).
"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from kavach.api import data
from kavach.api.envelope import (
    CLASSIFICATION_LABELS,
    ClassifiedValue,
    IntelligenceEnvelope,
    MethodInfo,
    classification_legend,
    envelope,
)
from kavach.api.main import app
from kavach.datagen.generator import generate_dataset
from kavach.provenance import DataClassification

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"

#: Every analytics route must answer with a top-level `intelligence` envelope.
ENVELOPED_ROUTES = [
    "/api/meta",
    "/api/cases",
    "/api/hotspots",
    "/api/trends",
    "/api/anomalies",
    "/api/districts",
    "/api/overview",
]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    out = tmp_path_factory.mktemp("envelope_synth")
    generate_dataset(out, MANIFEST, seed=20260718, background_cases=600)
    prev = os.environ.get("KAVACH_DATA_DIR")
    os.environ["KAVACH_DATA_DIR"] = str(out)
    data.enriched_cases.cache_clear()
    with TestClient(app) as c:
        yield c
    if prev is None:
        os.environ.pop("KAVACH_DATA_DIR", None)
    else:
        os.environ["KAVACH_DATA_DIR"] = prev
    data.enriched_cases.cache_clear()


# -- serializer units ----------------------------------------------------
def test_labels_cover_all_six_classes():
    assert set(CLASSIFICATION_LABELS) == set(DataClassification)
    assert all(CLASSIFICATION_LABELS[c] for c in DataClassification)


def test_envelope_fills_centralized_label():
    e = envelope(
        classification=DataClassification.STATISTICAL_INFERENCE,
        method_name="m",
        method_version="1.0.0",
    )
    assert e["classification"] == "STATISTICAL_INFERENCE"
    assert e["classification_label"] == CLASSIFICATION_LABELS[
        DataClassification.STATISTICAL_INFERENCE
    ]


def test_ai_derived_requires_confidence_and_model_version():
    with pytest.raises(ValidationError, match="model_version"):
        envelope(
            classification=DataClassification.AI_DERIVED,
            method_name="mo_extraction",
            method_version="1.0.0",
        )
    with pytest.raises(ValidationError, match="confidence"):
        ClassifiedValue(
            value="KNIFE",
            classification=DataClassification.AI_DERIVED,
            method=MethodInfo(
                method_name="mo_extraction", method_version="1.0.0", model_version="m1"
            ),
        )
    ok = ClassifiedValue(
        value="KNIFE",
        classification=DataClassification.AI_DERIVED,
        confidence=0.83,
        method=MethodInfo(
            method_name="mo_extraction", method_version="1.0.0", model_version="m1"
        ),
    )
    assert ok.classification_label == CLASSIFICATION_LABELS[DataClassification.AI_DERIVED]


def test_evidence_pointer_round_trip():
    e = envelope(
        classification=DataClassification.STATISTICAL_INFERENCE,
        method_name="m",
        method_version="1.0.0",
        run_id="r1",
        result_ref="hotspot:1",
        evidence_case_ids=(5, 6),
    )
    assert e["evidence"] == {
        "run_id": "r1",
        "result_ref": "hotspot:1",
        "evidence_case_ids": (5, 6),
    }


def test_case_detail_is_basic_and_enveloped(client):
    """PERF-001: a case click returns everything we know about the FIR — basics,
    people, narrative — as a plain FACT restatement (no graph metrics), and 404s
    for an unknown id (so a stale node click fails cleanly)."""
    first = client.get("/api/cases", params={"limit": 1, "with_coords": False})
    case_id = first.json()["cases"][0]["CaseMasterID"]

    resp = client.get(f"/api/cases/{case_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    case = body["case"]
    assert case["CaseMasterID"] == case_id
    # the fields the panel shows — present as keys (values may be null/empty)
    for k in ("CrimeNo", "district_name", "subhead_name", "status", "narrative"):
        assert k in case
    assert isinstance(case["accused"], list)
    assert isinstance(case["victims"], list)
    # a pure restatement — FACT, not an inference
    assert body["intelligence"]["classification"] == "FACT"

    missing = client.get("/api/cases/999999999")
    assert missing.status_code == 404


# -- router contract -----------------------------------------------------
@pytest.mark.parametrize("route", ENVELOPED_ROUTES)
def test_analytics_response_carries_valid_envelope(client, route):
    resp = client.get(route)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "intelligence" in body, f"{route} response lacks the intelligence envelope"
    parsed = IntelligenceEnvelope.model_validate(body["intelligence"])
    assert parsed.classification in DataClassification
    assert parsed.classification_label == CLASSIFICATION_LABELS[parsed.classification]
    assert parsed.method.method_name and parsed.method.method_version


def test_anomalies_envelope_is_statistical_with_model_provenance(client):
    """Detection is the explainable statistic (STATISTICAL_INFERENCE), but the
    corroborating IsolationForest's model_version must ride along for provenance."""
    body = client.get("/api/anomalies").json()
    env = IntelligenceEnvelope.model_validate(body["intelligence"])
    assert env.classification is DataClassification.STATISTICAL_INFERENCE
    assert env.method.model_version, "the ML model version must be carried"
    assert body["synthetic"] is True


def test_classification_legend_route_maps_one_to_one(client):
    resp = client.get("/api/classifications")
    assert resp.status_code == 200
    rows = resp.json()
    assert {r["classification"] for r in rows} == {c.value for c in DataClassification}
    for r in rows:
        assert r["label"] == CLASSIFICATION_LABELS[DataClassification(r["classification"])]
    assert len(rows) == len(classification_legend()) == 6


def test_envelope_documented_in_openapi(client):
    schema = client.get("/openapi.json").json()
    info = schema["components"]["schemas"]["ClassificationInfo"]
    assert set(info["properties"]) == {"classification", "label"}
    # examples per classification ship with the envelope model definition
    examples = IntelligenceEnvelope.model_json_schema().get("examples", [])
    assert {e["classification"] for e in examples} == {c.value for c in DataClassification}


def test_identities_list_omits_heavy_evidence(client):
    """The review queue must not ship members/signals for every candidate:
    that was 88% of a 1.1 MB response and made the tab look hung."""
    body = client.get("/api/identities").json()
    assert body["candidates"], "expected candidates"
    assert body["detail_omitted"] is True
    for c in body["candidates"]:
        assert "members" not in c and "signals" not in c
        assert c["cluster_id"] and c["name_variants"]  # list still renderable


def test_identity_detail_serves_evidence_per_candidate(client):
    listed = client.get("/api/identities").json()["candidates"][0]
    detail = client.get(f"/api/identities/{listed['cluster_id']}").json()
    assert detail["cluster_id"] == listed["cluster_id"]
    assert detail["members"] and detail["signals"]


def test_unknown_identity_cluster_404(client):
    assert client.get("/api/identities/no-such-cluster").status_code == 404


def test_identities_detail_flag_restores_full_payload(client):
    full = client.get("/api/identities", params={"detail": "true"}).json()
    assert "members" in full["candidates"][0]


# -- MO extraction API (MO-002/#38) ---------------------------------------
def test_mo_profile_serves_narrative_with_spans(client):
    from kavach.api.mo_routes import reset_mo_store

    reset_mo_store()
    listing = client.get("/api/v1/mo/profiles", params={"limit": 5}).json()
    assert listing["profiles"], "extraction should produce profiles"
    case_id = listing["profiles"][0]["case_master_id"]

    body = client.get(f"/api/v1/mo/{case_id}").json()
    assert body["narrative"]
    profile = body["profile"]
    assert profile["model_version"] and profile["extractor"] and profile["extracted_at"]
    # any span must index back into the narrative that produced it
    for key in ("crime_action", "target_type", "mobility"):
        span = profile[key].get("source_span")
        if span:
            assert body["narrative"][span[0] : span[1]]
    reset_mo_store()


def test_mo_response_is_ai_derived_with_model_version(client):
    """AI_DERIVED is refused by the envelope without a model_version."""
    env = IntelligenceEnvelope.model_validate(
        client.get("/api/v1/mo/runs/latest").json()["intelligence"]
    )
    assert env.classification is DataClassification.AI_DERIVED
    assert env.method.model_version


def test_mo_unknown_case_404(client):
    assert client.get("/api/v1/mo/99999999").status_code == 404


def test_mo_vocabulary_comes_from_the_schema(client):
    """Filter options must not drift from what the extractor may produce."""
    from kavach.analytics.mo.schema import MOBILITY

    vocab = client.get("/api/v1/mo/vocabulary").json()
    assert set(vocab) == {"crime_action", "target_type", "mobility"}
    assert set(vocab["mobility"]) <= set(MOBILITY)
    assert "motorcycle" in vocab["mobility"]


def test_mo_filters_narrow_results(client):
    from kavach.api.mo_routes import reset_mo_store

    reset_mo_store()
    everything = client.get("/api/v1/mo/profiles", params={"limit": 1}).json()["total"]
    filtered = client.get(
        "/api/v1/mo/profiles", params={"action": "snatching", "limit": 1}
    ).json()
    assert 0 < filtered["total"] < everything
    # and the filter is actually applied to the rows returned
    rows = client.get(
        "/api/v1/mo/profiles", params={"action": "snatching", "limit": 5}
    ).json()["profiles"]
    assert all(r["crime_action"]["value"] == "snatching" for r in rows)
    reset_mo_store()


def test_mo_pagination_returns_distinct_pages(client):
    first = client.get("/api/v1/mo/profiles", params={"limit": 5, "offset": 0}).json()
    second = client.get("/api/v1/mo/profiles", params={"limit": 5, "offset": 5}).json()
    ids_a = {p["case_master_id"] for p in first["profiles"]}
    ids_b = {p["case_master_id"] for p in second["profiles"]}
    assert ids_a and ids_b and not (ids_a & ids_b)
    assert first["total"] == second["total"] > 5
