"""Crime graph entities (GRAPH-001/#43) per derived-intelligence-schema.md.

Node identity for accused = Accused.AccusedMasterID — NEVER PersonID
(ADR-003; PersonID is a per-case ordering label and must not key nodes or
joins). Labels are aggregate-safe: no person names at state scope.

Every edge carries evidence_case_id + derivation + classification — no
unexplained edges. SECTION extends the boundary-doc node enum: issue #43
mandates LINKED_TO_SECTION edges from ActSectionAssociation, which need a
target node type for sections.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from kavach.provenance import DataClassification


class NodeType(StrEnum):
    CASE = "CASE"
    ACCUSED_RECORD = "ACCUSED_RECORD"
    VICTIM_RECORD = "VICTIM_RECORD"
    POLICE_STATION = "POLICE_STATION"
    DISTRICT = "DISTRICT"
    CRIME_HEAD = "CRIME_HEAD"
    CRIME_SUBHEAD = "CRIME_SUBHEAD"
    COURT = "COURT"
    SECTION = "SECTION"  # target of LINKED_TO_SECTION (issue #43 edge list)


class EdgeType(StrEnum):
    # observed (direct FK restatements)
    ACCUSED_IN = "ACCUSED_IN"
    VICTIM_IN = "VICTIM_IN"
    REGISTERED_AT = "REGISTERED_AT"
    OCCURRED_IN = "OCCURRED_IN"
    CLASSIFIED_AS = "CLASSIFIED_AS"
    LINKED_TO_SECTION = "LINKED_TO_SECTION"
    ARRESTED_IN = "ARRESTED_IN"
    PRODUCED_AT = "PRODUCED_AT"
    # derived
    SHARES_CASE_WITH = "SHARES_CASE_WITH"
    SIMILAR_MO = "SIMILAR_MO"  # produced by MO-004 (#40), not this projection


class Derivation(StrEnum):
    OBSERVED_FK = "OBSERVED_FK"
    CASE_CO_OCCURRENCE = "CASE_CO_OCCURRENCE"
    MO_SIMILARITY = "MO_SIMILARITY"  # reserved for #40


class CrimeGraphNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_id: str  # deterministic: f"{node_type}:{entity_ref_id}"
    node_type: NodeType
    entity_ref_id: str
    label: str


class CrimeGraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    edge_id: str  # deterministic: f"{type}|{source}|{target}|{evidence_case_id}"
    source_node_id: str
    target_node_id: str
    relationship_type: EdgeType
    weight: float = 1.0
    evidence_case_id: int  # mandatory — no unexplained edges
    derivation: Derivation
    classification: DataClassification


def node_id(node_type: NodeType, entity_ref_id: object) -> str:
    return f"{node_type.value}:{entity_ref_id}"


def edge_id(
    relationship_type: EdgeType, source: str, target: str, evidence_case_id: int
) -> str:
    return f"{relationship_type.value}|{source}|{target}|{evidence_case_id}"
