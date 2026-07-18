"""Crime graph persistence (GRAPH-001/#43) — DERIVED tables only.

Replace-by-run semantics: a successful projection atomically replaces the
previous graph; duplicate projection runs never accumulate rows. DB-level
NOT NULLs enforce the no-unexplained-edges rule (evidence_case_id,
derivation, classification).
"""

from __future__ import annotations

import sqlite3

from kavach.graph.models import CrimeGraphEdge, CrimeGraphNode, Derivation, EdgeType, NodeType
from kavach.provenance import DataClassification

_DDL = [
    """CREATE TABLE IF NOT EXISTS CrimeGraphNode (
        node_id TEXT PRIMARY KEY,
        node_type TEXT NOT NULL,
        entity_ref_id TEXT NOT NULL,
        label TEXT NOT NULL,
        run_id TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS CrimeGraphEdge (
        edge_id TEXT PRIMARY KEY,
        source_node_id TEXT NOT NULL,
        target_node_id TEXT NOT NULL,
        relationship_type TEXT NOT NULL,
        weight REAL NOT NULL,
        evidence_case_id INTEGER NOT NULL,
        derivation TEXT NOT NULL,
        classification TEXT NOT NULL,
        run_id TEXT NOT NULL
    )""",
]


class GraphRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        for ddl in _DDL:
            conn.execute(ddl)

    def replace_graph(
        self, run_id: str, nodes: list[CrimeGraphNode], edges: list[CrimeGraphEdge]
    ) -> None:
        """Atomically replace the whole graph with this run's projection."""
        with self._conn:
            self._conn.execute("DELETE FROM CrimeGraphEdge")
            self._conn.execute("DELETE FROM CrimeGraphNode")
            self._conn.executemany(
                "INSERT INTO CrimeGraphNode (node_id, node_type, entity_ref_id, label, run_id) "
                "VALUES (?, ?, ?, ?, ?)",
                [(n.node_id, n.node_type.value, n.entity_ref_id, n.label, run_id) for n in nodes],
            )
            self._conn.executemany(
                "INSERT INTO CrimeGraphEdge (edge_id, source_node_id, target_node_id, "
                "relationship_type, weight, evidence_case_id, derivation, classification, "
                "run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        e.edge_id,
                        e.source_node_id,
                        e.target_node_id,
                        e.relationship_type.value,
                        e.weight,
                        e.evidence_case_id,
                        e.derivation.value,
                        e.classification.value,
                        run_id,
                    )
                    for e in edges
                ],
            )

    def nodes(self) -> list[CrimeGraphNode]:
        rows = self._conn.execute("SELECT * FROM CrimeGraphNode ORDER BY node_id").fetchall()
        return [
            CrimeGraphNode(
                node_id=r["node_id"],
                node_type=NodeType(r["node_type"]),
                entity_ref_id=r["entity_ref_id"],
                label=r["label"],
            )
            for r in rows
        ]

    def edges(self, relationship_type: EdgeType | None = None) -> list[CrimeGraphEdge]:
        sql = "SELECT * FROM CrimeGraphEdge"
        params: tuple = ()
        if relationship_type is not None:
            sql += " WHERE relationship_type = ?"
            params = (relationship_type.value,)
        rows = self._conn.execute(sql + " ORDER BY edge_id", params).fetchall()
        return [
            CrimeGraphEdge(
                edge_id=r["edge_id"],
                source_node_id=r["source_node_id"],
                target_node_id=r["target_node_id"],
                relationship_type=EdgeType(r["relationship_type"]),
                weight=r["weight"],
                evidence_case_id=r["evidence_case_id"],
                derivation=Derivation(r["derivation"]),
                classification=DataClassification(r["classification"]),
            )
            for r in rows
        ]

    def graph_run_id(self) -> str | None:
        row = self._conn.execute("SELECT run_id FROM CrimeGraphNode LIMIT 1").fetchone()
        return None if row is None else row["run_id"]
