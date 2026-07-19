"""Design-review 1h: evidence browser API + persisted decisions contract."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kavach.api.audit_routes import reset_audit_repo
from kavach.api.graph_store import reset_graph_context
from kavach.api.main import app
from kavach.auth import Role, RoleAssignment, ScopeType
from kavach.datagen.generator import generate_dataset
from tests.conftest import TEST_USER_HEADER, install_test_auth, uninstall_test_auth

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    out = tmp_path_factory.mktemp("evidence_synth")
    generate_dataset(out, MANIFEST, seed=20260714, background_cases=300)
    prev = os.environ.get("KAVACH_DATA_DIR")
    os.environ["KAVACH_DATA_DIR"] = str(out)
    reset_graph_context()
    reset_audit_repo()
    headers = install_test_auth(
        RoleAssignment(
            user_id="evidence-admin", role=Role.SYSTEM_ADMIN, scope_type=ScopeType.STATE
        )
    )
    with TestClient(app, headers=headers) as c:
        yield c
    uninstall_test_auth()
    if prev is None:
        os.environ.pop("KAVACH_DATA_DIR", None)
    else:
        os.environ["KAVACH_DATA_DIR"] = prev
    reset_graph_context()
    reset_audit_repo()


def test_runs_listed_with_method_versions(client):
    r = client.get("/api/v1/evidence/runs")
    assert r.status_code == 200
    runs = r.json()["runs"]
    assert runs, "graph build should have produced provenance runs"
    for run in runs:
        assert run["method_name"] and run["method_version"]
        assert run["status"] in ("RUNNING", "COMPLETED", "FAILED")


def test_run_detail_walks_to_source_firs(client):
    runs = client.get("/api/v1/evidence/runs").json()["runs"]
    completed = next(r for r in runs if r["status"] == "COMPLETED")
    detail = client.get(f"/api/v1/evidence/runs/{completed['run_id']}").json()
    assert detail["run"]["method_version"]
    assert detail["evidence_count"] >= 1
    ev = detail["evidence"][0]
    assert ev["classification"]
    assert ev["evidence_case_ids"], "any AI output must walk to source FIRs"
    assert ev["evidence_case_total"] >= len(ev["evidence_case_ids"])


def test_unknown_run_404(client):
    assert client.get("/api/v1/evidence/runs/nope").status_code == 404


def test_latest_by_type(client):
    latest = client.get("/api/v1/evidence/latest").json()["latest"]
    assert any(entry["intelligence_type"] == "ASSOCIATION" for entry in latest)


def test_decision_persists_and_survives_reload(client):
    r = client.post(
        "/api/v1/decisions",
        json={"kind": "IDENTITY", "target_ref": "cluster-42", "decision": "CONFIRMED"},
    )
    assert r.status_code == 200 and r.json()["recorded"]
    r2 = client.post(
        "/api/v1/decisions",
        json={"kind": "ALERT_ACK", "target_ref": "alert-7", "decision": "ACKNOWLEDGED"},
    )
    assert r2.status_code == 200
    # restore map: both decisions present (simulates reload)
    decisions = {d["target_ref"]: d for d in client.get("/api/v1/decisions").json()["decisions"]}
    assert decisions["cluster-42"]["decision"] == "CONFIRMED"
    assert decisions["cluster-42"]["actor_id"] == "test-state-analyst"  # session identity
    assert decisions["alert-7"]["decision"] == "ACKNOWLEDGED"


def test_decision_writes_append_only_audit(client):
    client.post(
        "/api/v1/decisions",
        json={"kind": "IDENTITY", "target_ref": "cluster-9", "decision": "REJECTED"},
    )
    audit = client.get(
        "/api/v1/audit",
        params={"event_type": "IDENTITY_REVIEW_DECISION"},
        headers={TEST_USER_HEADER: "evidence-admin"},
    ).json()
    assert any("candidate:cluster-9" in e["target_refs"] for e in audit["events"])


def test_redecide_overwrites_state_keeps_audit_trail(client):
    for decision in ("CONFIRMED", "REJECTED"):
        client.post(
            "/api/v1/decisions",
            json={"kind": "IDENTITY", "target_ref": "cluster-flip", "decision": decision},
        )
    decisions = {d["target_ref"]: d for d in client.get("/api/v1/decisions").json()["decisions"]}
    assert decisions["cluster-flip"]["decision"] == "REJECTED"  # latest state wins
    audit = client.get(
        "/api/v1/audit",
        params={"event_type": "IDENTITY_REVIEW_DECISION"},
        headers={TEST_USER_HEADER: "evidence-admin"},
    ).json()
    flips = [e for e in audit["events"] if "candidate:cluster-flip" in e["target_refs"]]
    assert len(flips) == 2  # every action stays in the trail


def test_activity_feed_reflects_decisions(client):
    acts = client.get("/api/v1/evidence/activity").json()["activity"]
    assert any("cluster-42" in a["text"] for a in acts)
