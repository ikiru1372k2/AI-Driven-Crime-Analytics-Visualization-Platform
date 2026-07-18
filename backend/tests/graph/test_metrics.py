"""GRAPH-002/#44: metric correctness, determinism, vocabulary constraints."""

import re
from pathlib import Path

import pytest

from kavach.graph import (
    LIMITATION_OBSERVED_GRAPH,
    CrimeGraphEdge,
    CrimeGraphNode,
    Derivation,
    EdgeType,
    GraphRepository,
    MetricsRepository,
    NodeType,
    compute_metrics,
    project_graph,
)
from kavach.graph import metrics as metrics_mod
from kavach.provenance import (
    DataClassification,
    IntelligenceType,
    ProvenanceRepository,
    RunStatus,
)
from kavach.repositories.dev_fixture import connect

A = lambda i: f"ACCUSED_RECORD:{i}"  # noqa: E731


def _node(nid: str) -> CrimeGraphNode:
    return CrimeGraphNode(
        node_id=nid, node_type=NodeType.ACCUSED_RECORD,
        entity_ref_id=nid.split(":")[1], label=f"Accused record {nid.split(':')[1]}",
    )


def _edge(rel: EdgeType, a: str, b: str, case: int) -> CrimeGraphEdge:
    derived = rel is EdgeType.SIMILAR_MO
    return CrimeGraphEdge(
        edge_id=f"{rel.value}|{a}|{b}|{case}",
        source_node_id=a,
        target_node_id=b,
        relationship_type=rel,
        evidence_case_id=case,
        derivation=Derivation.MO_SIMILARITY if derived else Derivation.CASE_CO_OCCURRENCE,
        classification=(
            DataClassification.POTENTIAL_ASSOCIATION
            if derived
            else DataClassification.DERIVED_METRIC
        ),
    )


@pytest.fixture()
def bridge_world():
    """Ground-truth bridge topology (DATA-001 identity-fragment pattern):

    clique A (a1,a2,a3 — case 201) and clique B (b1,b2,b3 — case 202),
    joined only through FRAG via cross-case SIMILAR_MO links. Every
    A↔B path crosses FRAG → FRAG must rank top betweenness.
    """
    conn = connect()
    prov = ProvenanceRepository(conn)
    repo = GraphRepository(conn)
    share = EdgeType.SHARES_CASE_WITH
    sim = EdgeType.SIMILAR_MO
    edges = [
        _edge(share, A(1), A(2), 201), _edge(share, A(1), A(3), 201),
        _edge(share, A(2), A(3), 201),
        _edge(share, A(11), A(12), 202), _edge(share, A(11), A(13), 202),
        _edge(share, A(12), A(13), 202),
        _edge(sim, A(99), A(1), 201), _edge(sim, A(99), A(11), 202),
        # single-case complete clique (case 203) — mega-case artifact
        _edge(share, A(21), A(22), 203), _edge(share, A(21), A(23), 203),
        _edge(share, A(22), A(23), 203),
    ]
    nodes = sorted({n for e in edges for n in (e.source_node_id, e.target_node_id)})
    repo.replace_graph("proj-test", [_node(n) for n in nodes], edges)
    return conn, prov


def test_ground_truth_bridge_ranks_top_betweenness(bridge_world):
    conn, prov = bridge_world
    result = compute_metrics(conn, prov)
    by_id = {m.node_id: m for m in result.node_metrics}
    frag = by_id[A(99)]
    comp = [m for m in result.node_metrics if m.component_id == frag.component_id]
    top3 = sorted(comp, key=lambda m: m.betweenness, reverse=True)[:3]
    assert frag.node_id in {m.node_id for m in top3}
    assert frag.betweenness == max(m.betweenness for m in comp)
    assert frag.interpretation == metrics_mod.INTERPRETATION_BRIDGE


def test_components_communities_and_degree(bridge_world):
    conn, prov = bridge_world
    result = compute_metrics(conn, prov)
    by_id = {m.node_id: m for m in result.node_metrics}
    # two components: bridged 7-node structure + the 3-node artifact clique
    assert result.component_count == 2
    # Louvain (seeded) splits the bridged component into the two cliques
    assert by_id[A(1)].community_id == by_id[A(2)].community_id == by_id[A(3)].community_id
    assert by_id[A(11)].community_id == by_id[A(12)].community_id
    assert by_id[A(1)].community_id != by_id[A(11)].community_id
    # hand-computed degrees: a1 = 2 clique peers + frag = 3
    assert by_id[A(1)].degree == 3
    assert by_id[A(99)].degree == 2
    assert by_id[A(2)].degree == 2


def test_pair_jaccard_and_co_occurrence(bridge_world):
    conn, prov = bridge_world
    compute_metrics(conn, prov)
    rows = {(r["node_a"], r["node_b"]): r for r in MetricsRepository(conn).pair_metrics()}
    # hand-computed: N(a1)={a2,a3,frag}, N(a2)={a1,a3} → 1 common / 4 union
    r = rows[(A(1), A(2))]
    assert r["jaccard"] == pytest.approx(0.25)
    assert r["shared_case_count"] == 1
    assert r["classification"] == "DERIVED_METRIC"


def test_repeat_co_occurrence_counts_distinct_cases():
    conn = connect()
    prov = ProvenanceRepository(conn)
    repo = GraphRepository(conn)
    edges = [
        _edge(EdgeType.SHARES_CASE_WITH, A(1), A(2), 301),
        _edge(EdgeType.SHARES_CASE_WITH, A(1), A(2), 302),  # same pair, 2nd case
    ]
    repo.replace_graph("proj-test", [_node(A(1)), _node(A(2))], edges)
    result = compute_metrics(conn, prov)
    by_id = {m.node_id: m for m in result.node_metrics}
    assert by_id[A(1)].co_occurrence_count == 2
    (row,) = MetricsRepository(conn).pair_metrics()
    assert row["shared_case_count"] == 2
    # two distinct evidence cases → NOT a single-case artifact
    assert not by_id[A(1)].is_case_size_artifact


def test_mega_case_artifact_flagged_and_excluded_from_bridges(bridge_world):
    conn, prov = bridge_world
    result = compute_metrics(conn, prov)
    clique = [m for m in result.node_metrics if m.node_id in {A(21), A(22), A(23)}]
    assert all(m.is_case_size_artifact for m in clique)
    assert all(m.interpretation == metrics_mod.INTERPRETATION_ARTIFACT for m in clique)
    assert all(m.interpretation != metrics_mod.INTERPRETATION_BRIDGE for m in clique)


def test_metrics_deterministic_across_runs(bridge_world):
    conn, prov = bridge_world
    r1 = compute_metrics(conn, prov)
    rows1 = [tuple(r)[2:] for r in MetricsRepository(conn).node_metrics()]  # skip run_id
    r2 = compute_metrics(conn, prov)
    rows2 = [tuple(r)[2:] for r in MetricsRepository(conn).node_metrics()]
    assert r1.run_id != r2.run_id
    assert rows1 == rows2  # identical incl. community assignment (seeded Louvain)


def test_rows_carry_method_version_and_run_id(bridge_world):
    conn, prov = bridge_world
    result = compute_metrics(conn, prov)
    repo = MetricsRepository(conn)
    for r in repo.node_metrics():
        assert r["run_id"] == result.run_id
        assert r["method_version"] == metrics_mod.METHOD_VERSION
        assert r["classification"] == "STATISTICAL_INFERENCE"
    for r in repo.pair_metrics():
        assert r["run_id"] == result.run_id
        assert r["method_version"] == metrics_mod.METHOD_VERSION


def test_provenance_run_and_limitation_string(bridge_world):
    conn, prov = bridge_world
    result = compute_metrics(conn, prov)
    run = prov.get_run(result.run_id)
    assert run.status is RunStatus.COMPLETED
    assert run.intelligence_type is IntelligenceType.ASSOCIATION
    assert LIMITATION_OBSERVED_GRAPH in result.limitations
    evidence = prov.evidence_for_run(result.run_id)
    assert len(evidence) == result.component_count
    for ev in evidence:
        assert LIMITATION_OBSERVED_GRAPH in ev.limitations
        assert ev.evidence_case_ids  # every component cites its cases
    # artifact clique component cites exactly its single case
    artifact_ev = next(e for e in evidence if e.evidence_case_ids == (203,))
    assert artifact_ev.result_ref == f"component:{A(21)}"


def test_prohibited_vocabulary_absent():
    """Interpretation constraint lint: no criminological role claims in any
    graph/API/UI copy string (issue #44 PROHIBITED list; #63 UI copy AC)."""
    prohibited = re.compile(r"gang\s*leader|mastermind|kingpin", re.IGNORECASE)
    graph_dir = Path(metrics_mod.__file__).parent
    api_dir = graph_dir.parent / "api"
    frontend_src = graph_dir.parents[3] / "frontend" / "src"
    files = [*graph_dir.glob("*.py"), *api_dir.glob("*.py")]
    files += [*frontend_src.rglob("*.ts"), *frontend_src.rglob("*.tsx")]
    assert files
    for path in sorted(files):
        assert not prohibited.search(path.read_text()), path


def test_empty_graph_and_projection_integration():
    """No co-occurrence edges → zero components; end-to-end with the real
    projection all pure SHARES_CASE_WITH components are per-case cliques."""
    from tests.graph.test_projection import _seed_fixture

    conn = connect()
    prov = ProvenanceRepository(conn)
    empty = compute_metrics(conn, prov)
    assert empty.component_count == 0 and empty.node_metrics == []

    _seed_fixture(conn)
    project_graph(conn, prov)
    result = compute_metrics(conn, prov)
    assert result.projection_run_id is not None
    # schema property (ADR-003): SHARES_CASE_WITH-only graphs are single-case
    # cliques, so every component is flagged as a case-size artifact
    assert result.component_count == 2  # case 101 triangle + case 102 pair
    assert all(m.is_case_size_artifact for m in result.node_metrics)
