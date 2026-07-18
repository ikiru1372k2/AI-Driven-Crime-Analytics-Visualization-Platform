"""Graph metrics over the accused co-occurrence subgraph (GRAPH-002/#44).

Computes per-projection metrics with NetworkX: connected components, degree
centrality, betweenness (exact ≤ BETWEENNESS_EXACT_MAX nodes per component,
else sampled k=min(500, n), seeded), Louvain communities (seeded,
deterministic), pair co-occurrence frequency and Jaccard common-neighbour
similarity. Rows persist with method version + run_id (replace-by-run).

Subgraph: SHARES_CASE_WITH edges, plus SIMILAR_MO edges when present
(MO-004/#40). Note a structural property (ADR-003): accused records are
per-case, so SHARES_CASE_WITH alone yields disjoint per-case cliques —
cross-case structure (and therefore meaningful bridge ranking) appears once
cross-case derived edges join the subgraph. Components that are single-case
cliques are flagged as case-size artifacts and excluded from bridge ranking
(documented rule below).

INTERPRETATION CONSTRAINTS: metric labels use a fixed vocabulary that
describes the observed record graph only. Criminological role claims are
prohibited (vocabulary lint test in tests/graph/test_metrics.py).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime

import networkx as nx

from kavach.graph.models import EdgeType
from kavach.graph.repository import GraphRepository
from kavach.provenance import (
    DataClassification,
    Factor,
    IntelligenceType,
    ProvenanceRepository,
    intelligence_run,
)

METHOD_NAME = "networkx_co_occurrence_metrics"
METHOD_VERSION = "1.0.0"

#: Deterministic seed for sampled betweenness and Louvain communities.
SEED = 20260718
#: Exact betweenness up to this component size; larger components sample.
BETWEENNESS_EXACT_MAX = 2000
#: A node is a "hub" when it co-occurs with at least this many records.
HUB_DEGREE_MIN = 3
#: Bridge interpretation: top-N betweenness within a component.
BRIDGE_TOP_N = 3

#: Fixed interpretation vocabulary — the ONLY strings the API/UI may attach
#: to metric values. Describes graph structure, never criminal roles.
INTERPRETATION_BRIDGE = "high-connectivity bridge in the observed case-association graph"
INTERPRETATION_HUB = "frequently co-occurring accused record"
INTERPRETATION_ARTIFACT = "single-case clique — case-size artifact, excluded from bridge ranking"

#: Shipped with every metrics response (issue #44 non-goal guard).
LIMITATION_OBSERVED_GRAPH = (
    "Metrics describe the observed record graph, not real-world social structure"
)

_DDL = [
    """CREATE TABLE IF NOT EXISTS CrimeGraphNodeMetric (
        node_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        component_id TEXT NOT NULL,
        community_id TEXT NOT NULL,
        degree INTEGER NOT NULL,
        degree_centrality REAL NOT NULL,
        betweenness REAL NOT NULL,
        co_occurrence_count INTEGER NOT NULL,
        is_case_size_artifact INTEGER NOT NULL,
        interpretation TEXT,
        classification TEXT NOT NULL,
        method_version TEXT NOT NULL,
        PRIMARY KEY (node_id, run_id)
    )""",
    """CREATE TABLE IF NOT EXISTS CrimeGraphPairMetric (
        node_a TEXT NOT NULL,
        node_b TEXT NOT NULL,
        run_id TEXT NOT NULL,
        shared_case_count INTEGER NOT NULL,
        jaccard REAL NOT NULL,
        classification TEXT NOT NULL,
        method_version TEXT NOT NULL,
        PRIMARY KEY (node_a, node_b, run_id)
    )""",
]


@dataclass
class NodeMetric:
    node_id: str
    component_id: str
    community_id: str
    degree: int
    degree_centrality: float
    betweenness: float
    co_occurrence_count: int
    is_case_size_artifact: bool
    interpretation: str | None


@dataclass
class MetricsResult:
    run_id: str
    projection_run_id: str | None
    component_count: int = 0
    node_metrics: list[NodeMetric] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


class MetricsRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        for ddl in _DDL:
            conn.execute(ddl)

    def replace_metrics(
        self,
        run_id: str,
        nodes: list[NodeMetric],
        pairs: list[tuple[str, str, int, float]],
    ) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM CrimeGraphNodeMetric")
            self._conn.execute("DELETE FROM CrimeGraphPairMetric")
            self._conn.executemany(
                "INSERT INTO CrimeGraphNodeMetric (node_id, run_id, component_id, "
                "community_id, degree, degree_centrality, betweenness, "
                "co_occurrence_count, is_case_size_artifact, interpretation, "
                "classification, method_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        m.node_id, run_id, m.component_id, m.community_id, m.degree,
                        m.degree_centrality, m.betweenness, m.co_occurrence_count,
                        int(m.is_case_size_artifact), m.interpretation,
                        DataClassification.STATISTICAL_INFERENCE.value, METHOD_VERSION,
                    )
                    for m in nodes
                ],
            )
            self._conn.executemany(
                "INSERT INTO CrimeGraphPairMetric (node_a, node_b, run_id, "
                "shared_case_count, jaccard, classification, method_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (a, b, run_id, shared, jac, DataClassification.DERIVED_METRIC.value,
                     METHOD_VERSION)
                    for a, b, shared, jac in pairs
                ],
            )

    def node_metrics(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM CrimeGraphNodeMetric ORDER BY node_id"
        ).fetchall()

    def pair_metrics(self) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM CrimeGraphPairMetric ORDER BY node_a, node_b"
        ).fetchall()


def _co_occurrence_graph(graph_repo: GraphRepository) -> tuple[nx.Graph, dict]:
    """Undirected weighted graph over accused records.

    Edge weight = distinct shared cases (SHARES_CASE_WITH) plus cross-case
    similarity links (SIMILAR_MO) when present. Each edge tracks its
    evidence case ids for artifact detection and provenance.
    """
    g: nx.Graph = nx.Graph()
    evidence: dict[tuple[str, str], set[int]] = {}
    for edge_type in (EdgeType.SHARES_CASE_WITH, EdgeType.SIMILAR_MO):
        for e in graph_repo.edges(edge_type):
            key = tuple(sorted((e.source_node_id, e.target_node_id)))
            evidence.setdefault(key, set()).add(e.evidence_case_id)
    for (a, b), cases in sorted(evidence.items()):
        g.add_edge(a, b, weight=len(cases))
    return g, evidence


def _is_case_size_artifact(component: set[str], g: nx.Graph, evidence: dict) -> bool:
    """Documented rule: a component whose edges all derive from ONE case and
    which forms a complete graph is a mega-case artifact — its (zero)
    betweenness and clique density say nothing about cross-case structure."""
    sub = g.subgraph(component)
    cases = {
        c for a, b in sub.edges() for c in evidence[tuple(sorted((a, b)))]
    }
    n = len(component)
    return len(cases) == 1 and sub.number_of_edges() == n * (n - 1) // 2


def compute_metrics(
    conn: sqlite3.Connection, provenance: ProvenanceRepository
) -> MetricsResult:
    """Compute + persist metrics for the current projection (replace-by-run)."""
    graph_repo = GraphRepository(conn)
    metrics_repo = MetricsRepository(conn)
    projection_run_id = graph_repo.graph_run_id()
    g, evidence = _co_occurrence_graph(graph_repo)

    limitations = [LIMITATION_OBSERVED_GRAPH]
    node_metrics: list[NodeMetric] = []
    pair_rows: list[tuple[str, str, int, float]] = []
    components = sorted(nx.connected_components(g), key=min)
    degree_centrality = nx.degree_centrality(g) if g else {}

    per_component: list[tuple[str, set[str], bool, set[int]]] = []
    for comp in components:
        comp_id = min(comp)
        artifact = _is_case_size_artifact(comp, g, evidence)
        sub = g.subgraph(comp)
        comp_cases = {
            c for a, b in sub.edges() for c in evidence[tuple(sorted((a, b)))]
        }
        per_component.append((comp_id, comp, artifact, comp_cases))

        # betweenness: exact for small components, sampled (seeded) beyond
        n = len(comp)
        k = None if n <= BETWEENNESS_EXACT_MAX else min(500, n)
        if k is not None:
            limitations.append(
                f"component {comp_id}: betweenness sampled k={k} of {n} (seed {SEED})"
            )
        betweenness = nx.betweenness_centrality(sub, k=k, seed=SEED, weight=None)

        # communities: Louvain, seeded → deterministic
        communities = sorted(
            nx.community.louvain_communities(sub, weight="weight", seed=SEED), key=min
        )
        community_of = {
            node: f"{comp_id}/c{i}" for i, comm in enumerate(communities) for node in comm
        }

        bridge_cutoff = sorted(
            (betweenness[v] for v in comp), reverse=True
        )[:BRIDGE_TOP_N]
        for v in sorted(comp):
            deg = sub.degree(v)
            co_count = int(sum(d["weight"] for _, _, d in sub.edges(v, data=True)))
            interpretation: str | None = None
            if artifact:
                interpretation = INTERPRETATION_ARTIFACT
            elif (
                betweenness[v] > 0.0
                and bridge_cutoff
                and betweenness[v] >= bridge_cutoff[-1]
            ):
                interpretation = INTERPRETATION_BRIDGE
            elif deg >= HUB_DEGREE_MIN:
                interpretation = INTERPRETATION_HUB
            node_metrics.append(
                NodeMetric(
                    node_id=v,
                    component_id=comp_id,
                    community_id=community_of[v],
                    degree=deg,
                    degree_centrality=degree_centrality[v],
                    betweenness=betweenness[v],
                    co_occurrence_count=co_count,
                    is_case_size_artifact=artifact,
                    interpretation=interpretation,
                )
            )

        # pair metrics: co-occurrence frequency + Jaccard for connected pairs
        pairs = [tuple(sorted((a, b))) for a, b in sub.edges()]
        jaccard = {(a, b): j for a, b, j in nx.jaccard_coefficient(sub, pairs)}
        for a, b in sorted(pairs):
            pair_rows.append(
                (a, b, len(evidence[(a, b)]), round(jaccard[(a, b)], 6))
            )

    window = provenance.get_run(projection_run_id) if projection_run_id else None
    with intelligence_run(
        provenance,
        intelligence_type=IntelligenceType.ASSOCIATION,
        method_name=METHOD_NAME,
        method_version=METHOD_VERSION,
        analysis_window_from=(
            window.analysis_window_from if window else datetime(1970, 1, 1, tzinfo=UTC)
        ),
        analysis_window_to=(
            window.analysis_window_to if window else datetime(1970, 1, 1, tzinfo=UTC)
        ),
    ) as run:
        for comp_id, comp, artifact, comp_cases in per_component:
            run.emit(
                result_ref=f"component:{comp_id}",
                evidence_case_ids=sorted(comp_cases),
                factors=[
                    Factor(name="node_count", contribution=float(len(comp))),
                    Factor(name="case_size_artifact", contribution=float(artifact)),
                ],
                limitations=limitations,
                classification=DataClassification.STATISTICAL_INFERENCE,
            )
        metrics_repo.replace_metrics(run.run_id, node_metrics, pair_rows)

    return MetricsResult(
        run_id=run.run_id,
        projection_run_id=projection_run_id,
        component_count=len(components),
        node_metrics=node_metrics,
        limitations=limitations,
    )
