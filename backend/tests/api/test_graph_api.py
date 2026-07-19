"""GRAPH-003/#45 contract tests: subgraph, node detail, scope, latency."""

import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kavach.api.envelope import IntelligenceEnvelope
from kavach.api.graph_store import graph_context, reset_graph_context
from kavach.api.main import app
from kavach.datagen.generator import generate_dataset
from kavach.graph import LIMITATION_OBSERVED_GRAPH
from tests.conftest import install_test_auth, uninstall_test_auth

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"

EDGE_FIELDS = {
    "edge_id", "source", "target", "relationship_type", "weight",
    "evidence_case_id", "derivation", "classification",
}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    out = tmp_path_factory.mktemp("graph_api_synth")
    generate_dataset(out, MANIFEST, seed=20260714, background_cases=400)
    prev = os.environ.get("KAVACH_DATA_DIR")
    os.environ["KAVACH_DATA_DIR"] = str(out)
    reset_graph_context()
    headers = install_test_auth()
    with TestClient(app, headers=headers) as c:
        yield c
    uninstall_test_auth()
    if prev is None:
        os.environ.pop("KAVACH_DATA_DIR", None)
    else:
        os.environ["KAVACH_DATA_DIR"] = prev
    reset_graph_context()


@pytest.fixture(scope="module")
def ground_truth(client):
    """A multi-accused case from the generated data: (case_id, accused_ids,
    district_id) — the co-accused clique the subgraph must return."""
    ctx = graph_context()
    conn = ctx.metrics._conn
    row = conn.execute(
        "SELECT CaseMasterID AS cid, COUNT(*) AS n FROM Accused "
        "GROUP BY CaseMasterID HAVING n BETWEEN 2 AND 10 ORDER BY cid LIMIT 1"
    ).fetchone()
    accused = [
        r["AccusedMasterID"]
        for r in conn.execute(
            "SELECT AccusedMasterID FROM Accused WHERE CaseMasterID = ? "
            "ORDER BY AccusedMasterID",
            (row["cid"],),
        )
    ]
    return row["cid"], accused, ctx.case_district[row["cid"]]


def test_depth2_subgraph_returns_co_accused_clique(client, ground_truth):
    case_id, accused, _ = ground_truth
    seed = accused[0]
    r = client.get(
        "/api/v1/graph/subgraph",
        params={"seed_type": "ACCUSED_RECORD", "seed_id": seed, "depth": 2},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    node_ids = {n["node_id"] for n in body["nodes"]}
    # all co-accused of the ground-truth case are present…
    assert {f"ACCUSED_RECORD:{a}" for a in accused} <= node_ids
    # …the case node arrives via ACCUSED_IN at depth 1
    assert f"CASE:{case_id}" in node_ids
    rels = {e["relationship_type"] for e in body["edges"]}
    assert "SHARES_CASE_WITH" in rels and "ACCUSED_IN" in rels
    # co-accused edges cite the ground-truth case
    shares = [e for e in body["edges"] if e["relationship_type"] == "SHARES_CASE_WITH"]
    assert all(e["evidence_case_id"] == case_id for e in shares)


def test_depth1_includes_induced_edges_between_leaves(client, ground_truth):
    """Regression: SHARES_CASE_WITH pairs between two depth-1 accused must
    appear even though neither leaf is expanded (induced edge set)."""
    case_id, accused, _ = ground_truth
    r = client.get(
        "/api/v1/graph/subgraph",
        params={"seed_type": "CASE", "seed_id": case_id, "depth": 1, "limit": 500},
    )
    body = r.json()
    shares = [e for e in body["edges"] if e["relationship_type"] == "SHARES_CASE_WITH"]
    n = len(accused)
    assert len(shares) == n * (n - 1) // 2  # complete co-accused pair set


def test_every_edge_carries_full_provenance_fields(client, ground_truth):
    _, accused, _ = ground_truth
    r = client.get(
        "/api/v1/graph/subgraph",
        params={"seed_type": "ACCUSED_RECORD", "seed_id": accused[0]},
    )
    body = r.json()
    assert body["edges"], "expected edges in subgraph"
    for e in body["edges"]:
        assert EDGE_FIELDS <= set(e)
        assert e["evidence_case_id"] is not None
    parsed = IntelligenceEnvelope.model_validate(body["intelligence"])
    assert LIMITATION_OBSERVED_GRAPH in parsed.limitations


def test_seed_not_found_404_and_depth_cap_422(client):
    r = client.get(
        "/api/v1/graph/subgraph",
        params={"seed_type": "ACCUSED_RECORD", "seed_id": 99999999},
    )
    assert r.status_code == 404
    r = client.get(
        "/api/v1/graph/subgraph",
        params={"seed_type": "ACCUSED_RECORD", "seed_id": 1, "depth": 3},
    )
    assert r.status_code == 422  # hard depth cap


def test_limit_produces_stubs_not_silent_truncation(client, ground_truth):
    case_id, accused, _ = ground_truth
    r = client.get(
        "/api/v1/graph/subgraph",
        params={"seed_type": "CASE", "seed_id": case_id, "depth": 1, "limit": 2},
    )
    body = r.json()
    assert body["node_count"] <= 2
    truncated = body["stubs"]["truncated"]
    assert truncated and truncated[0]["node_id"] == f"CASE:{case_id}"
    assert truncated[0]["more_edges"] > 0


def test_node_detail_metrics_and_evidence(client, ground_truth):
    case_id, accused, _ = ground_truth
    r = client.get(f"/api/v1/graph/nodes/ACCUSED_RECORD/{accused[0]}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["node"]["node_type"] == "ACCUSED_RECORD"
    assert case_id in body["linked_cases"]
    m = body["metrics"]
    assert m is not None
    assert m["method_version"] and m["run_id"]
    assert m["degree"] == len(accused) - 1  # clique peers
    env = IntelligenceEnvelope.model_validate(body["intelligence"])
    assert env.evidence.result_ref == f"ACCUSED_RECORD:{accused[0]}"
    assert case_id in env.evidence.evidence_case_ids


def test_node_detail_404(client):
    assert client.get("/api/v1/graph/nodes/ACCUSED_RECORD/99999999").status_code == 404


# NOTE: cross-scope isolation moved to tests/api/test_auth_api.py — scope is
# now resolved from the caller's role assignment (CAT-003/#19), so it can no
# longer be exercised with a query parameter.

def test_latency_p95_under_800ms(client, ground_truth):
    case_id, accused, _ = ground_truth
    timings = []
    for _ in range(20):
        t0 = time.perf_counter()
        r = client.get(
            "/api/v1/graph/subgraph",
            params={"seed_type": "ACCUSED_RECORD", "seed_id": accused[0], "depth": 2},
        )
        timings.append(time.perf_counter() - t0)
        assert r.status_code == 200
    timings.sort()
    p95 = timings[int(len(timings) * 0.95) - 1]
    assert p95 < 0.8, f"p95 {p95:.3f}s exceeds 800ms budget"


def test_openapi_documents_graph_routes(client):
    schema = client.get("/openapi.json").json()
    assert "/api/v1/graph/subgraph" in schema["paths"]
    assert "/api/v1/graph/nodes/{node_type}/{ref_id}" in schema["paths"]
