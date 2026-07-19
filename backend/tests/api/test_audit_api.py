"""PROV-003/#26 audit query API — authorization under CAT-003/#19 auth.

Role is no longer client-supplied: it comes from the caller's stored role
assignment, so a header can no longer claim SYSTEM_ADMIN.
"""

import pytest
from fastapi.testclient import TestClient

from kavach.api.audit_routes import audit_repo, reset_audit_repo
from kavach.api.main import app
from kavach.auth import Role, RoleAssignment, ScopeType
from kavach.provenance.audit import record_identity_review
from tests.conftest import TEST_USER_HEADER, install_test_auth, uninstall_test_auth

ADMIN = {TEST_USER_HEADER: "audit-admin"}
ANALYST = {TEST_USER_HEADER: "audit-analyst"}

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_store():
    reset_audit_repo()
    install_test_auth(
        RoleAssignment(user_id="audit-admin", role=Role.SYSTEM_ADMIN, scope_type=ScopeType.STATE),
        RoleAssignment(
            user_id="audit-analyst",
            role=Role.DISTRICT_ANALYST,
            scope_type=ScopeType.DISTRICT,
            scope_id=44,
        ),
    )
    yield
    uninstall_test_auth()
    reset_audit_repo()


def test_query_without_authentication_is_401():
    assert client.get("/api/v1/audit").status_code == 401


def test_non_admin_role_forbidden():
    assert client.get("/api/v1/audit", headers=ANALYST).status_code == 403


def test_role_cannot_be_claimed_by_header():
    """The pre-#19 X-KAVACH-ROLE seam must not grant privilege any more."""
    r = client.get("/api/v1/audit", headers={**ANALYST, "X-KAVACH-ROLE": "SYSTEM_ADMIN"})
    assert r.status_code == 403


def test_unassigned_user_forbidden():
    r = client.get("/api/v1/audit", headers={TEST_USER_HEADER: "no-such-user"})
    assert r.status_code == 403


def test_admin_reads_recorded_events():
    record_identity_review(
        audit_repo(),
        actor_id="reviewer-9",
        actor_role="DISTRICT_ANALYST",
        candidate_id="cand-7",
        decision="NEEDS_MORE_EVIDENCE",
    )
    r = client.get("/api/v1/audit", headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    (e,) = body["events"]
    assert e["event_type"] == "IDENTITY_REVIEW_DECISION"
    assert e["actor_id"] == "reviewer-9"
    assert e["target_refs"] == ["candidate:cand-7"]


def test_event_type_filter():
    record_identity_review(
        audit_repo(),
        actor_id="a",
        actor_role="DISTRICT_ANALYST",
        candidate_id="c",
        decision="CONFIRMED",
    )
    r = client.get(
        "/api/v1/audit", params={"event_type": "REPORT_GENERATION"}, headers=ADMIN
    )
    assert r.status_code == 200 and r.json()["count"] == 0
