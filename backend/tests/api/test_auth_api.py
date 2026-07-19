"""CAT-003/#19: request-level auth contract — 401/403, scope isolation.

Uses a mocked validator (issue #19 test plan) so identity is controlled
without a live Catalyst session.
"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kavach.api.audit_routes import reset_audit_repo
from kavach.api.graph_store import graph_context, reset_graph_context
from kavach.api.main import app
from kavach.auth import (
    Identity,
    InvalidToken,
    Role,
    RoleAssignment,
    ScopeType,
    reset_role_repo,
    role_repo,
    set_validator,
)
from kavach.datagen.generator import generate_dataset

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"

#: the mock reads this header; a request without it is unauthenticated
USER_HEADER = "x-test-user"


class MockValidator:
    """Stands in for Catalyst Auth: header → identity, nothing else."""

    def validate(self, headers: dict[str, str]) -> Identity:
        user = headers.get(USER_HEADER)
        if not user:
            raise InvalidToken("no token")
        if user == "expired":
            raise InvalidToken("token expired")
        return Identity(user_id=user, email=f"{user}@demo.invalid")


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    out = tmp_path_factory.mktemp("auth_synth")
    generate_dataset(out, MANIFEST, seed=20260714, background_cases=300)
    prev = os.environ.get("KAVACH_DATA_DIR")
    os.environ["KAVACH_DATA_DIR"] = str(out)
    reset_graph_context()
    reset_audit_repo()
    reset_role_repo()
    set_validator(MockValidator())

    repo = role_repo()
    repo.assign(
        RoleAssignment(user_id="state", role=Role.SCRB_STATE_ANALYST, scope_type=ScopeType.STATE)
    )
    repo.assign(
        RoleAssignment(user_id="admin", role=Role.SYSTEM_ADMIN, scope_type=ScopeType.STATE)
    )
    with TestClient(app) as c:
        yield c

    set_validator(None)
    reset_role_repo()
    reset_audit_repo()
    reset_graph_context()
    if prev is None:
        os.environ.pop("KAVACH_DATA_DIR", None)
    else:
        os.environ["KAVACH_DATA_DIR"] = prev


def _auth(user: str) -> dict:
    return {USER_HEADER: user}


@pytest.fixture(scope="module")
def district_user(client):
    """A district-scoped analyst confined to the seed case's district."""
    ctx = graph_context()
    case_id, district = next(iter(sorted(ctx.case_district.items())))
    role_repo().assign(
        RoleAssignment(
            user_id="district",
            role=Role.DISTRICT_ANALYST,
            scope_type=ScopeType.DISTRICT,
            scope_id=district,
        )
    )
    other = next(d for d in sorted(set(ctx.case_district.values())) if d != district)
    role_repo().assign(
        RoleAssignment(
            user_id="other-district",
            role=Role.DISTRICT_ANALYST,
            scope_type=ScopeType.DISTRICT,
            scope_id=other,
        )
    )
    return {"case_id": case_id, "district": district, "other": other}


# -- 401: no / bad token ---------------------------------------------------
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/graph/subgraph?seed_type=CASE&seed_id=5001",
        "/api/v1/graph/nodes/CASE/5001",
        "/api/v1/audit",
    ],
)
def test_request_without_token_is_401(client, path):
    assert client.get(path).status_code == 401


def test_expired_token_is_401(client):
    r = client.get("/api/v1/audit", headers=_auth("expired"))
    assert r.status_code == 401
    assert "expired" in r.json()["detail"]


# -- 403: authenticated but unauthorized -----------------------------------
def test_authenticated_without_assignment_is_403(client):
    r = client.get("/api/v1/audit", headers=_auth("nobody"))
    assert r.status_code == 403
    assert "no role assignment" in r.json()["detail"]


def test_audit_requires_admin_role(client):
    assert client.get("/api/v1/audit", headers=_auth("state")).status_code == 403
    assert client.get("/api/v1/audit", headers=_auth("admin")).status_code == 200


def test_role_cannot_be_claimed_by_header(client):
    """The pre-#19 header seam must no longer grant privilege."""
    r = client.get(
        "/api/v1/audit",
        headers={**_auth("state"), "X-KAVACH-ROLE": "SYSTEM_ADMIN"},
    )
    assert r.status_code == 403


# -- scope enforcement (server-resolved) -----------------------------------
def test_statewide_role_sees_unscoped_graph(client, district_user):
    r = client.get(
        "/api/v1/graph/subgraph",
        params={"seed_type": "CASE", "seed_id": district_user["case_id"], "limit": 300},
        headers=_auth("state"),
    )
    assert r.status_code == 200
    assert r.json()["scope_district_id"] is None


def test_district_role_is_confined_to_its_district(client, district_user):
    ctx = graph_context()
    r = client.get(
        "/api/v1/graph/subgraph",
        params={"seed_type": "CASE", "seed_id": district_user["case_id"], "limit": 300},
        headers=_auth("district"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["scope_district_id"] == district_user["district"]
    for e in body["edges"]:
        assert ctx.case_district[e["evidence_case_id"]] == district_user["district"]


def test_cross_district_node_detail_is_403(client, district_user):
    """A district analyst cannot read another district's node detail."""
    r = client.get(
        f"/api/v1/graph/nodes/CASE/{district_user['case_id']}",
        headers=_auth("other-district"),
    )
    assert r.status_code == 403
    # the legitimate owner can
    ok = client.get(
        f"/api/v1/graph/nodes/CASE/{district_user['case_id']}",
        headers=_auth("district"),
    )
    assert ok.status_code == 200


def test_client_cannot_widen_its_own_scope(client, district_user):
    """A scope query param must not override the assigned scope."""
    r = client.get(
        "/api/v1/graph/subgraph",
        params={
            "seed_type": "CASE",
            "seed_id": district_user["case_id"],
            "limit": 300,
            "scope_district_id": "",  # attempt to clear the scope
        },
        headers=_auth("district"),
    )
    assert r.status_code == 200
    assert r.json()["scope_district_id"] == district_user["district"]


# -- decisions are attributed to the session, not the client ---------------
def test_decision_actor_comes_from_session(client):
    r = client.post(
        "/api/v1/decisions",
        json={"kind": "IDENTITY", "target_ref": "cluster-auth", "decision": "CONFIRMED"},
        headers={**_auth("state"), "X-KAVACH-ACTOR": "someone-else"},
    )
    assert r.status_code == 200
    audit = client.get(
        "/api/v1/audit",
        params={"event_type": "IDENTITY_REVIEW_DECISION"},
        headers=_auth("admin"),
    ).json()
    entry = next(e for e in audit["events"] if "candidate:cluster-auth" in e["target_refs"])
    assert entry["actor_id"] == "state"  # not the spoofed header value
    assert entry["actor_role"] == Role.SCRB_STATE_ANALYST.value


def test_decisions_require_authentication(client):
    r = client.post(
        "/api/v1/decisions",
        json={"kind": "ALERT_ACK", "target_ref": "a1", "decision": "ACKNOWLEDGED"},
    )
    assert r.status_code == 401
