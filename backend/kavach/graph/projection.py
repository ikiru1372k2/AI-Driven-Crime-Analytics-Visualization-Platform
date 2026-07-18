"""Deterministic graph projection (GRAPH-001/#43).

Projects relational source records into CrimeGraphNode/CrimeGraphEdge under
an IntelligenceRun (#24, type ASSOCIATION). Rules:

- Reproducible: same source rows → identical node/edge sets (deterministic
  IDs, ordered scans). Replace-by-run: each successful projection replaces
  the previous graph.
- Accused node identity = AccusedMasterID. PersonID is never read here
  (ADR-003 guard test scans this module).
- Every edge carries evidence_case_id + derivation + classification.
- Dangling FKs are skipped and counted, never guessed.
- Cases with more than MAX_PAIRWISE_ACCUSED accused would emit C(n,2)
  SHARES_CASE_WITH edges; they are aggregated instead: no pairwise edges,
  a documented limitation entry on the run's evidence.

Observed edges restate FK columns (FACT/OBSERVED_FK). Derived
SHARES_CASE_WITH edges are DERIVED_METRIC/CASE_CO_OCCURRENCE, one edge per
co-accused pair per shared case. SIMILAR_MO edges belong to MO-004 (#40).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import combinations

from kavach.graph.models import (
    CrimeGraphEdge,
    CrimeGraphNode,
    Derivation,
    EdgeType,
    NodeType,
    edge_id,
    node_id,
)
from kavach.graph.repository import GraphRepository
from kavach.provenance import (
    DataClassification,
    Factor,
    IntelligenceType,
    ProvenanceRepository,
    intelligence_run,
)

METHOD_NAME = "relational_graph_projection"
METHOD_VERSION = "1.0.0"

#: Pairwise SHARES_CASE_WITH cap: a 50-accused case means C(50,2)=1225 edges.
MAX_PAIRWISE_ACCUSED = 20


@dataclass
class ProjectionResult:
    run_id: str
    node_count: int = 0
    edge_count: int = 0
    skipped_dangling: dict[str, int] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)


def _int(v: object) -> int | None:
    """Defensive int parse — source values may arrive as strings ('' = null)."""
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class _Builder:
    """Accumulates a deterministic node/edge set."""

    def __init__(self) -> None:
        self.nodes: dict[str, CrimeGraphNode] = {}
        self.edges: dict[str, CrimeGraphEdge] = {}
        self.skipped: dict[str, int] = {}

    def skip(self, kind: str) -> None:
        self.skipped[kind] = self.skipped.get(kind, 0) + 1

    def node(self, node_type: NodeType, ref: object, label: str) -> str:
        nid = node_id(node_type, ref)
        if nid not in self.nodes:
            self.nodes[nid] = CrimeGraphNode(
                node_id=nid, node_type=node_type, entity_ref_id=str(ref), label=label
            )
        return nid

    def edge(
        self,
        rel: EdgeType,
        source: str,
        target: str,
        evidence_case_id: int,
        *,
        derivation: Derivation = Derivation.OBSERVED_FK,
        classification: DataClassification = DataClassification.FACT,
        weight: float = 1.0,
    ) -> None:
        eid = edge_id(rel, source, target, evidence_case_id)
        if eid not in self.edges:
            self.edges[eid] = CrimeGraphEdge(
                edge_id=eid,
                source_node_id=source,
                target_node_id=target,
                relationship_type=rel,
                weight=weight,
                evidence_case_id=evidence_case_id,
                derivation=derivation,
                classification=classification,
            )


def _lookup(conn: sqlite3.Connection, sql: str) -> dict[int, sqlite3.Row]:
    out: dict[int, sqlite3.Row] = {}
    for row in conn.execute(sql):
        key = _int(row[0])
        if key is not None:
            out[key] = row
    return out


def project_graph(
    conn: sqlite3.Connection, provenance: ProvenanceRepository
) -> ProjectionResult:
    """Project the relational store into the crime graph (replace-by-run)."""
    graph_repo = GraphRepository(conn)
    b = _Builder()

    cases = _lookup(conn, "SELECT * FROM CaseMaster ORDER BY CaseMasterID")
    stations = _lookup(conn, "SELECT UnitID, UnitName, DistrictID FROM Unit ORDER BY UnitID")
    districts = _lookup(
        conn, "SELECT DistrictID, DistrictName FROM District ORDER BY DistrictID"
    )
    heads = _lookup(conn, "SELECT CrimeHeadID, CrimeGroupName FROM CrimeHead ORDER BY CrimeHeadID")
    subheads = _lookup(
        conn, "SELECT CrimeSubHeadID, CrimeHeadName FROM CrimeSubHead ORDER BY CrimeSubHeadID"
    )
    courts = _lookup(conn, "SELECT CourtID, CourtName FROM Court ORDER BY CourtID")

    # -- case-anchored observed edges -----------------------------------
    for cid, case in cases.items():
        case_node = b.node(NodeType.CASE, cid, f"Case {cid}")

        sid = _int(case["PoliceStationID"])
        if sid is not None:
            if sid in stations:
                st = b.node(
                    NodeType.POLICE_STATION, sid, stations[sid]["UnitName"] or f"Unit {sid}"
                )
                b.edge(EdgeType.REGISTERED_AT, case_node, st, cid)
                did = _int(stations[sid]["DistrictID"])
                if did is not None:
                    if did in districts:
                        dn = b.node(
                            NodeType.DISTRICT,
                            did,
                            districts[did]["DistrictName"] or f"District {did}",
                        )
                        b.edge(EdgeType.OCCURRED_IN, case_node, dn, cid)
                    else:
                        b.skip("OCCURRED_IN:district")
            else:
                b.skip("REGISTERED_AT:station")

        hid = _int(case["CrimeMajorHeadID"])
        if hid is not None:
            if hid in heads:
                hn = b.node(
                    NodeType.CRIME_HEAD, hid, heads[hid]["CrimeGroupName"] or f"Crime head {hid}"
                )
                b.edge(EdgeType.CLASSIFIED_AS, case_node, hn, cid)
            else:
                b.skip("CLASSIFIED_AS:head")
        shid = _int(case["CrimeMinorHeadID"])
        if shid is not None:
            if shid in subheads:
                sn = b.node(
                    NodeType.CRIME_SUBHEAD,
                    shid,
                    subheads[shid]["CrimeHeadName"] or f"Crime sub-head {shid}",
                )
                b.edge(EdgeType.CLASSIFIED_AS, case_node, sn, cid)
            else:
                b.skip("CLASSIFIED_AS:subhead")

    # -- accused records + co-occurrence ---------------------------------
    accused_by_case: dict[int, list[int]] = {}
    for row in conn.execute(
        "SELECT AccusedMasterID, CaseMasterID FROM Accused ORDER BY AccusedMasterID"
    ):
        amid, cid = _int(row["AccusedMasterID"]), _int(row["CaseMasterID"])
        if amid is None or cid is None or cid not in cases:
            b.skip("ACCUSED_IN:case")
            continue
        # identity = AccusedMasterID (ADR-003); label is aggregate-safe (no name)
        an = b.node(NodeType.ACCUSED_RECORD, amid, f"Accused record {amid}")
        b.edge(EdgeType.ACCUSED_IN, an, node_id(NodeType.CASE, cid), cid)
        accused_by_case.setdefault(cid, []).append(amid)

    capped_cases: list[tuple[int, int]] = []
    for cid in sorted(accused_by_case):
        members = sorted(accused_by_case[cid])
        if len(members) < 2:
            continue  # a single-accused case yields no SHARES_CASE_WITH
        if len(members) > MAX_PAIRWISE_ACCUSED:
            capped_cases.append((cid, len(members)))
            continue
        for a, bb in combinations(members, 2):
            b.edge(
                EdgeType.SHARES_CASE_WITH,
                node_id(NodeType.ACCUSED_RECORD, a),
                node_id(NodeType.ACCUSED_RECORD, bb),
                cid,
                derivation=Derivation.CASE_CO_OCCURRENCE,
                classification=DataClassification.DERIVED_METRIC,
            )

    # -- victim records ---------------------------------------------------
    for row in conn.execute(
        "SELECT VictimMasterID, CaseMasterID FROM Victim ORDER BY VictimMasterID"
    ):
        vmid, cid = _int(row["VictimMasterID"]), _int(row["CaseMasterID"])
        if vmid is None or cid is None or cid not in cases:
            b.skip("VICTIM_IN:case")
            continue
        # aggregate-safe label: no names at state scope
        vn = b.node(NodeType.VICTIM_RECORD, vmid, f"Victim record {vmid}")
        b.edge(EdgeType.VICTIM_IN, vn, node_id(NodeType.CASE, cid), cid)

    # -- act/section links -------------------------------------------------
    for row in conn.execute(
        "SELECT CaseMasterID, ActID, SectionID FROM ActSectionAssociation "
        "ORDER BY CaseMasterID, ActOrderID, SectionOrderID"
    ):
        cid = _int(row["CaseMasterID"])
        act, sec = row["ActID"], row["SectionID"]
        if cid is None or cid not in cases or act in (None, "") or sec in (None, ""):
            b.skip("LINKED_TO_SECTION")
            continue
        ref = f"{act}:{sec}"
        sn = b.node(NodeType.SECTION, ref, f"Act {act} Sec {sec}")
        b.edge(EdgeType.LINKED_TO_SECTION, node_id(NodeType.CASE, cid), sn, cid)

    # -- arrest/surrender events -------------------------------------------
    for row in conn.execute(
        "SELECT * FROM ArrestSurrender ORDER BY ArrestSurrenderID"
    ):
        cid, amid = _int(row["CaseMasterID"]), _int(row["AccusedMasterID"])
        if cid is None or cid not in cases or amid is None:
            b.skip("ARRESTED_IN:case_or_accused")
            continue
        an = node_id(NodeType.ACCUSED_RECORD, amid)
        if an not in b.nodes:
            b.skip("ARRESTED_IN:unknown_accused")
            continue
        sid = _int(row["PoliceStationID"])
        if sid is not None:
            if sid in stations:
                st = b.node(
                    NodeType.POLICE_STATION, sid, stations[sid]["UnitName"] or f"Unit {sid}"
                )
                b.edge(EdgeType.ARRESTED_IN, an, st, cid)
            else:
                b.skip("ARRESTED_IN:station")
        crid = _int(row["CourtID"])
        if crid is not None:
            if crid in courts:
                cn = b.node(NodeType.COURT, crid, courts[crid]["CourtName"] or f"Court {crid}")
                b.edge(EdgeType.PRODUCED_AT, an, cn, cid)
            else:
                b.skip("PRODUCED_AT:court")

    # -- persist under a provenance run (replace-by-run) --------------------
    dates = [
        datetime.fromisoformat(str(c["CrimeRegisteredDate"]))
        for c in cases.values()
        if c["CrimeRegisteredDate"] not in (None, "")
    ]
    window_from = min(dates) if dates else datetime(1970, 1, 1, tzinfo=UTC)
    window_to = max(dates) if dates else datetime(1970, 1, 1, tzinfo=UTC)

    limitations = [f"case {cid}: {n} accused exceeds pairwise cap "
                   f"({MAX_PAIRWISE_ACCUSED}) — SHARES_CASE_WITH aggregated, not emitted"
                   for cid, n in capped_cases]

    nodes = [b.nodes[k] for k in sorted(b.nodes)]
    edges = [b.edges[k] for k in sorted(b.edges)]

    with intelligence_run(
        provenance,
        intelligence_type=IntelligenceType.ASSOCIATION,
        method_name=METHOD_NAME,
        method_version=METHOD_VERSION,
        analysis_window_from=window_from,
        analysis_window_to=window_to,
    ) as run:
        for e in edges:
            if e.relationship_type is EdgeType.SHARES_CASE_WITH:
                run.emit(
                    result_ref=e.edge_id,
                    evidence_case_ids=[e.evidence_case_id],
                    factors=[Factor(name="shared_case", contribution=1.0, direction="UP")],
                    limitations=limitations,
                    classification=DataClassification.DERIVED_METRIC,
                )
        if cases:
            run.emit(
                result_ref=f"graph:{run.run_id}",
                evidence_case_ids=sorted(cases),
                factors=[
                    Factor(name="node_count", contribution=float(len(nodes))),
                    Factor(name="edge_count", contribution=float(len(edges))),
                ],
                limitations=limitations
                + [f"skipped dangling {k}: {v}" for k, v in sorted(b.skipped.items())],
                classification=DataClassification.FACT,
            )
        graph_repo.replace_graph(run.run_id, nodes, edges)

    return ProjectionResult(
        run_id=run.run_id,
        node_count=len(nodes),
        edge_count=len(edges),
        skipped_dangling=b.skipped,
        limitations=limitations,
    )
