"""GRAPH-001/#43 acceptance tests: projection rules, determinism, guards."""

import sqlite3
from pathlib import Path

import pytest

from kavach.graph import EdgeType, GraphRepository, NodeType, project_graph
from kavach.graph import projection as projection_mod
from kavach.provenance import (
    DataClassification,
    IntelligenceType,
    ProvenanceRepository,
    RunStatus,
)
from kavach.repositories.dev_fixture import connect

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"


def _seed_fixture(conn: sqlite3.Connection) -> None:
    """Small relational world: 2 districts, 2 stations, courts, 3 cases.

    Case 101: accused 1,2,3 (co-accused triangle) + victim 11, sections, arrest.
    Case 102: accused 4,5 (pair) — accused 4 shares PersonID label 'A1' with
              accused 1 (ADR-003: must stay distinct nodes).
    Case 103: single accused 6 (no SHARES_CASE_WITH).
    Accused 7 dangles (case 999 does not exist).
    """
    conn.executemany(
        "INSERT INTO District (DistrictID, DistrictName, StateID, Active) VALUES (?, ?, 1, 1)",
        [(44, "Bengaluru City"), (12, "Mysuru")],
    )
    conn.executemany(
        "INSERT INTO Unit (UnitID, UnitName, TypeID, DistrictID, Active) "
        "VALUES (?, ?, 1, ?, 1)",
        [(7, "Peenya PS", 44), (8, "Vijayanagar PS", 12)],
    )
    conn.execute(
        "INSERT INTO Court (CourtID, CourtName, DistrictID, StateID, Active) "
        "VALUES (21, 'City Civil Court', 44, 1, 1)"
    )
    conn.execute(
        "INSERT INTO CrimeHead (CrimeHeadID, CrimeGroupName, Active) VALUES (3, 'Robbery', 1)"
    )
    conn.execute(
        "INSERT INTO CrimeSubHead (CrimeSubHeadID, CrimeHeadID, CrimeHeadName, SeqID) "
        "VALUES (71, 3, 'Highway Robbery', 1)"
    )
    conn.executemany(
        "INSERT INTO CaseMaster (CaseMasterID, CrimeNo, CrimeRegisteredDate, "
        "PoliceStationID, CrimeMajorHeadID, CrimeMinorHeadID) VALUES (?, ?, ?, ?, 3, 71)",
        [
            (101, "0042/2025", "2025-02-01T10:00:00", 7),
            (102, "0043/2025", "2025-02-11T09:30:00", 8),
            (103, "0044/2025", "2025-03-01T18:00:00", 7),
        ],
    )
    conn.executemany(
        "INSERT INTO Accused (AccusedMasterID, CaseMasterID, AccusedName, PersonID) "
        "VALUES (?, ?, ?, ?)",
        [
            (1, 101, "Name One", "A1"),
            (2, 101, "Name Two", "A2"),
            (3, 101, "Name Three", "A3"),
            (4, 102, "Name Four", "A1"),  # same PersonID label as accused 1
            (5, 102, "Name Five", "A2"),
            (6, 103, "Name Six", "A1"),
            (7, 999, "Dangling", "A1"),  # dangling case FK
        ],
    )
    conn.execute(
        "INSERT INTO Victim (VictimMasterID, CaseMasterID, VictimName) "
        "VALUES (11, 101, 'Victim Name')"
    )
    conn.executemany(
        "INSERT INTO ActSectionAssociation (CaseMasterID, ActID, SectionID, "
        "ActOrderID, SectionOrderID) VALUES (?, ?, ?, 1, ?)",
        [(101, 1, 392, 1), (101, 1, 397, 2)],
    )
    conn.execute(
        "INSERT INTO ArrestSurrender (ArrestSurrenderID, CaseMasterID, "
        "PoliceStationID, CourtID, AccusedMasterID, IsAccused) "
        "VALUES (1, 101, 7, 21, 1, 1)"
    )


@pytest.fixture()
def world():
    conn = connect()
    _seed_fixture(conn)
    return conn, ProvenanceRepository(conn)


def test_observed_edges_projected(world):
    conn, prov = world
    project_graph(conn, prov)
    repo = GraphRepository(conn)
    rels = {e.relationship_type for e in repo.edges()}
    assert {
        EdgeType.ACCUSED_IN, EdgeType.VICTIM_IN, EdgeType.REGISTERED_AT,
        EdgeType.OCCURRED_IN, EdgeType.CLASSIFIED_AS, EdgeType.LINKED_TO_SECTION,
        EdgeType.ARRESTED_IN, EdgeType.PRODUCED_AT, EdgeType.SHARES_CASE_WITH,
    } <= rels
    # every observed edge is a FACT restatement with its evidence case
    for e in repo.edges():
        assert e.evidence_case_id in (101, 102, 103)
        if e.relationship_type is not EdgeType.SHARES_CASE_WITH:
            assert e.classification is DataClassification.FACT
            assert e.derivation.value == "OBSERVED_FK"


def test_co_accused_chain_with_correct_evidence(world):
    conn, prov = world
    project_graph(conn, prov)
    repo = GraphRepository(conn)
    shares = repo.edges(EdgeType.SHARES_CASE_WITH)
    pairs = {(e.source_node_id, e.target_node_id, e.evidence_case_id) for e in shares}
    a = lambda i: f"ACCUSED_RECORD:{i}"  # noqa: E731
    assert pairs == {
        (a(1), a(2), 101), (a(1), a(3), 101), (a(2), a(3), 101),  # triangle
        (a(4), a(5), 102),  # pair
    }
    for e in shares:
        assert e.classification is DataClassification.DERIVED_METRIC
        assert e.derivation.value == "CASE_CO_OCCURRENCE"
    # single-accused case 103 contributes none
    assert not any(e.evidence_case_id == 103 for e in shares)


def test_personid_never_keys_node_identity(world):
    conn, prov = world
    project_graph(conn, prov)
    repo = GraphRepository(conn)
    accused_nodes = [n for n in repo.nodes() if n.node_type is NodeType.ACCUSED_RECORD]
    # accused 1, 4, 6 share PersonID label "A1" yet remain distinct nodes
    assert {n.entity_ref_id for n in accused_nodes} == {"1", "2", "3", "4", "5", "6"}
    # no cross-case SHARES_CASE_WITH edge between same-PersonID records
    shares = repo.edges(EdgeType.SHARES_CASE_WITH)
    assert ("ACCUSED_RECORD:1", "ACCUSED_RECORD:4") not in {
        (e.source_node_id, e.target_node_id) for e in shares
    }


def test_personid_guard_source_scan():
    """Static guard (ADR-003): projection code never touches PersonID.

    AST-based: docstrings are stripped so only executable code is scanned —
    no SQL string, attribute or identifier may reference PersonID.
    """
    import ast

    tree = ast.parse(Path(projection_mod.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
            ):
                node.body = node.body[1:]  # drop docstring
    assert "PersonID" not in ast.dump(tree)


def test_labels_are_aggregate_safe(world):
    conn, prov = world
    project_graph(conn, prov)
    for n in GraphRepository(conn).nodes():
        if n.node_type in (NodeType.ACCUSED_RECORD, NodeType.VICTIM_RECORD):
            assert "Name" not in n.label  # no person names at state scope


def test_edge_without_evidence_case_id_rejected(world):
    conn, prov = world
    project_graph(conn, prov)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO CrimeGraphEdge (edge_id, source_node_id, target_node_id, "
            "relationship_type, weight, evidence_case_id, derivation, classification, "
            "run_id) VALUES ('x', 'a', 'b', 'ACCUSED_IN', 1.0, NULL, 'OBSERVED_FK', "
            "'FACT', 'r')"
        )


def test_dangling_fk_skipped_and_counted(world):
    conn, prov = world
    result = project_graph(conn, prov)
    assert result.skipped_dangling.get("ACCUSED_IN:case") == 1
    repo = GraphRepository(conn)
    assert "ACCUSED_RECORD:7" not in {n.node_id for n in repo.nodes()}


def test_reprojection_is_deterministic_and_replaces_by_run(world):
    conn, prov = world
    r1 = project_graph(conn, prov)
    repo = GraphRepository(conn)
    nodes1, edges1 = repo.nodes(), repo.edges()
    r2 = project_graph(conn, prov)
    assert r2.run_id != r1.run_id
    # identical node/edge sets (IDs deterministic, independent of run)
    assert repo.nodes() == nodes1
    assert repo.edges() == edges1
    # replace-by-run: the stored graph belongs to the latest run only
    assert repo.graph_run_id() == r2.run_id


def test_pairwise_cap_documented_aggregation(world):
    conn, prov = world
    cap = projection_mod.MAX_PAIRWISE_ACCUSED
    conn.execute(
        "INSERT INTO CaseMaster (CaseMasterID, CrimeRegisteredDate, PoliceStationID, "
        "CrimeMajorHeadID, CrimeMinorHeadID) VALUES (200, '2025-04-01T00:00:00', 7, 3, 71)"
    )
    conn.executemany(
        "INSERT INTO Accused (AccusedMasterID, CaseMasterID, AccusedName) VALUES (?, 200, 'X')",
        [(1000 + i,) for i in range(cap + 1)],
    )
    result = project_graph(conn, prov)
    shares = GraphRepository(conn).edges(EdgeType.SHARES_CASE_WITH)
    assert not any(e.evidence_case_id == 200 for e in shares)
    assert any("case 200" in lim and "cap" in lim for lim in result.limitations)


def test_projection_runs_under_provenance(world):
    conn, prov = world
    result = project_graph(conn, prov)
    run = prov.get_run(result.run_id)
    assert run.status is RunStatus.COMPLETED
    assert run.method_version == projection_mod.METHOD_VERSION
    assert prov.latest_completed_run(IntelligenceType.ASSOCIATION).run_id == result.run_id
    # each derived edge has an evidence row citing its case
    shares = GraphRepository(conn).edges(EdgeType.SHARES_CASE_WITH)
    for e in shares:
        (ev,) = prov.evidence_for_result(e.edge_id, run_id=result.run_id)
        assert ev.evidence_case_ids == (e.evidence_case_id,)


def test_full_synthetic_projection_complete_and_deterministic(tmp_path):
    """Integration: generate → ingest → project; co-accused completeness."""
    from kavach.datagen.generator import generate_dataset
    from kavach.ingestion.loader import load_dataset

    out = tmp_path / "synth"
    generate_dataset(out, MANIFEST, seed=20260714, background_cases=300)
    conn = connect()
    load_dataset(out, MANIFEST, conn)
    prov = ProvenanceRepository(conn)
    result = project_graph(conn, prov)
    assert result.node_count > 0 and result.edge_count > 0

    repo = GraphRepository(conn)
    shares = repo.edges(EdgeType.SHARES_CASE_WITH)
    by_case: dict[int, set[tuple[str, str]]] = {}
    for e in shares:
        by_case.setdefault(e.evidence_case_id, set()).add(
            (e.source_node_id, e.target_node_id)
        )
    # every multi-accused case (within cap) projects its complete pair set
    rows = conn.execute(
        "SELECT CaseMasterID, COUNT(*) AS n FROM Accused "
        "WHERE CaseMasterID IN (SELECT CaseMasterID FROM CaseMaster) "
        "GROUP BY CaseMasterID HAVING n >= 2"
    ).fetchall()
    assert rows, "synthetic dataset should contain multi-accused cases"
    for r in rows:
        n = r["n"]
        if n <= projection_mod.MAX_PAIRWISE_ACCUSED:
            expected = n * (n - 1) // 2
            assert len(by_case.get(r["CaseMasterID"], set())) == expected

    # determinism across re-projection on unchanged data
    edges1 = repo.edges()
    project_graph(conn, prov)
    assert repo.edges() == edges1
