"""PROV-003/#26: audit query API authz contract (SYSTEM_ADMIN only)."""

import pytest
from fastapi.testclient import TestClient

from kavach.api.audit_routes import audit_repo, reset_audit_repo
from kavach.api.main import app
from kavach.provenance.audit import record_identity_review

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_store():
    reset_audit_repo()
    yield
    reset_audit_repo()


def test_query_without_role_forbidden():
    assert client.get("/api/v1/audit").status_code == 403


def test_query_with_non_admin_role_forbidden():
    for role in ("STATE", "DISTRICT", "UNIT", "analyst"):
        r = client.get("/api/v1/audit", headers={"X-KAVACH-ROLE": role})
        assert r.status_code == 403, role


def test_admin_reads_recorded_events():
    record_identity_review(
        audit_repo(),
        actor_id="reviewer-9",
        actor_role="DISTRICT",
        candidate_id="cand-7",
        decision="NEEDS_MORE_EVIDENCE",
    )
    r = client.get("/api/v1/audit", headers={"X-KAVACH-ROLE": "SYSTEM_ADMIN"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    (e,) = body["events"]
    assert e["event_type"] == "IDENTITY_REVIEW_DECISION"
    assert e["actor_id"] == "reviewer-9"
    assert e["target_refs"] == ["candidate:cand-7"]


def test_event_type_filter():
    record_identity_review(
        audit_repo(), actor_id="a", actor_role="DISTRICT", candidate_id="c", decision="CONFIRMED"
    )
    r = client.get(
        "/api/v1/audit",
        params={"event_type": "REPORT_GENERATION"},
        headers={"X-KAVACH-ROLE": "SYSTEM_ADMIN"},
    )
    assert r.status_code == 200 and r.json()["count"] == 0
