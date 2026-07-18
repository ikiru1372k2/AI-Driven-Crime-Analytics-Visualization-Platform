"""Graph exploration API (GRAPH-003/#45): scoped subgraph, node detail.

Contract (issue #45):
- GET /api/v1/graph/subgraph?seed_type=&seed_id=&depth<=2&limit=
- GET /api/v1/graph/nodes/{node_id}

Every edge in a response carries relationship_type, derivation,
evidence_case_id and classification; every response carries the #25
intelligence envelope and the observed-graph limitation string (#44).

Scope enforcement: `scope_district_id` restricts results to cases of that
district — cross-scope edges are stubbed with a count, never detailed, and
out-of-scope node detail is 403. The parameter is the enforcement seam for
Catalyst Authentication (CAT-003/#19): once roles land, the value comes
from the authenticated identity instead of the query string.
"""

from __future__ import annotations

from collections import deque

from fastapi import APIRouter, HTTPException, Query

from kavach.api.envelope import envelope
from kavach.api.graph_store import GraphContext, graph_context
from kavach.graph import LIMITATION_OBSERVED_GRAPH, CrimeGraphEdge, NodeType
from kavach.graph import metrics as metrics_mod
from kavach.provenance import DataClassification

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])

#: Hard caps (issue #45 edge case: depth explosion).
MAX_DEPTH = 2
MAX_NODES = 500
DEFAULT_NODES = 150

SCOPE_LIMITATION = (
    "scope_district_id is caller-supplied until Catalyst Authentication "
    "(CAT-003/#19) binds it to the authenticated role"
)


def _edge_payload(e: CrimeGraphEdge) -> dict:
    return {
        "edge_id": e.edge_id,
        "source": e.source_node_id,
        "target": e.target_node_id,
        "relationship_type": e.relationship_type.value,
        "weight": e.weight,
        "evidence_case_id": e.evidence_case_id,
        "derivation": e.derivation.value,
        "classification": e.classification.value,
    }


def _in_scope(ctx: GraphContext, e: CrimeGraphEdge, scope_district_id: int | None) -> bool:
    if scope_district_id is None:
        return True
    return ctx.case_district.get(e.evidence_case_id) == scope_district_id


def _envelope(ctx: GraphContext, extra_limitations: tuple[str, ...] = ()) -> dict:
    return envelope(
        classification=DataClassification.DERIVED_METRIC,
        method_name="graph_subgraph_retrieval",
        method_version="1.0.0",
        run_id=ctx.metrics_run_id,
        limitations=(LIMITATION_OBSERVED_GRAPH, *extra_limitations),
    )


@router.get("/subgraph")
def get_subgraph(
    seed_type: NodeType,
    seed_id: str,
    depth: int = Query(default=MAX_DEPTH, ge=1, le=MAX_DEPTH),
    limit: int = Query(default=DEFAULT_NODES, ge=1, le=MAX_NODES),
    scope_district_id: int | None = Query(default=None),
) -> dict:
    """BFS subgraph around a seed node (deterministic order, hard-capped).

    Nodes beyond `limit` and cross-scope edges are stubbed with counts
    ("N more"), never silently dropped.
    """
    ctx = graph_context()
    seed = f"{seed_type.value}:{seed_id}"
    if seed not in ctx.nodes:
        raise HTTPException(status_code=404, detail=f"unknown node {seed}")

    included: dict[str, int] = {seed: 0}
    edges: dict[str, CrimeGraphEdge] = {}
    truncated: dict[str, int] = {}
    cross_scope: dict[str, int] = {}
    frontier = deque([seed])
    while frontier:
        current = frontier.popleft()
        d = included[current]
        if d >= depth:
            continue
        for e in sorted(ctx.adjacency.get(current, []), key=lambda x: x.edge_id):
            if not _in_scope(ctx, e, scope_district_id):
                cross_scope[current] = cross_scope.get(current, 0) + 1
                continue
            other = e.target_node_id if e.source_node_id == current else e.source_node_id
            if other not in included and len(included) >= limit:
                truncated[current] = truncated.get(current, 0) + 1
                continue
            edges[e.edge_id] = e
            if other not in included:
                included[other] = d + 1
                frontier.append(other)

    return {
        "synthetic": True,
        "seed": seed,
        "depth": depth,
        "scope_district_id": scope_district_id,
        "node_count": len(included),
        "nodes": [
            {
                "node_id": nid,
                "node_type": ctx.nodes[nid].node_type.value,
                "entity_ref_id": ctx.nodes[nid].entity_ref_id,
                "label": ctx.nodes[nid].label,
                "depth": included[nid],
            }
            for nid in sorted(included)
        ],
        "edges": [_edge_payload(e) for _, e in sorted(edges.items())],
        "stubs": {
            "truncated": [
                {"node_id": n, "more_edges": c} for n, c in sorted(truncated.items())
            ],
            "cross_scope": [
                {"node_id": n, "cross_scope_edges": c}
                for n, c in sorted(cross_scope.items())
            ],
        },
        "intelligence": _envelope(
            ctx,
            (SCOPE_LIMITATION,) if scope_district_id is not None else (),
        ),
    }


@router.get("/nodes/{node_type}/{ref_id}")
def get_node_detail(
    node_type: NodeType,
    ref_id: str,
    scope_district_id: int | None = Query(default=None),
) -> dict:
    """Node detail: metrics (#44), linked cases (evidence), interpretation."""
    ctx = graph_context()
    node_id = f"{node_type.value}:{ref_id}"
    node = ctx.nodes.get(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"unknown node {node_id}")

    node_edges = sorted(ctx.adjacency.get(node_id, []), key=lambda e: e.edge_id)
    linked_cases = sorted({e.evidence_case_id for e in node_edges})
    if node.node_type is NodeType.CASE:
        linked_cases = sorted(set(linked_cases) | {int(node.entity_ref_id)})

    if scope_district_id is not None:
        in_scope = [
            c for c in linked_cases if ctx.case_district.get(c) == scope_district_id
        ]
        if not in_scope:
            # cross-scope leakage guard: existence yes (404 vs 403), detail no
            raise HTTPException(
                status_code=403,
                detail=f"node {node_id} has no cases within district scope "
                f"{scope_district_id}",
            )
        linked_cases = in_scope
        node_edges = [e for e in node_edges if _in_scope(ctx, e, scope_district_id)]

    m = ctx.node_metrics.get(node_id)
    metrics_block = None
    if m is not None:
        metrics_block = {
            "component_id": m["component_id"],
            "community_id": m["community_id"],
            "degree": m["degree"],
            "degree_centrality": m["degree_centrality"],
            "betweenness": m["betweenness"],
            "co_occurrence_count": m["co_occurrence_count"],
            "is_case_size_artifact": bool(m["is_case_size_artifact"]),
            "interpretation": m["interpretation"],
            "classification": m["classification"],
            "method_version": m["method_version"],
            "run_id": m["run_id"],
        }

    edge_type_counts: dict[str, int] = {}
    for e in node_edges:
        edge_type_counts[e.relationship_type.value] = (
            edge_type_counts.get(e.relationship_type.value, 0) + 1
        )

    return {
        "synthetic": True,
        "node": {
            "node_id": node.node_id,
            "node_type": node.node_type.value,
            "entity_ref_id": node.entity_ref_id,
            "label": node.label,
        },
        "scope_district_id": scope_district_id,
        "metrics": metrics_block,
        "linked_cases": linked_cases,
        "edge_type_counts": edge_type_counts,
        "edges": [_edge_payload(e) for e in node_edges],
        "intelligence": envelope(
            classification=DataClassification.DERIVED_METRIC,
            method_name=metrics_mod.METHOD_NAME,
            method_version=metrics_mod.METHOD_VERSION,
            run_id=ctx.metrics_run_id,
            result_ref=node_id,
            evidence_case_ids=tuple(linked_cases),
            limitations=(
                LIMITATION_OBSERVED_GRAPH,
                *((SCOPE_LIMITATION,) if scope_district_id is not None else ()),
            ),
        ),
    }
