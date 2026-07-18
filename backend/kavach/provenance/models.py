"""Provenance core models (PROV-001/#24) per derived-intelligence-schema.md.

Everything here is DERIVED (boundary doc): produced by KAVACH analytics,
never part of the source FIR ER schema, never mutating source tables.
Every derived row is traceable: run_id → method version → evidence case IDs.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DataClassification(StrEnum):
    """Six-class data classification (ADR-009, boundary doc)."""

    FACT = "FACT"
    DERIVED_METRIC = "DERIVED_METRIC"
    STATISTICAL_INFERENCE = "STATISTICAL_INFERENCE"
    AI_DERIVED = "AI_DERIVED"
    POTENTIAL_ASSOCIATION = "POTENTIAL_ASSOCIATION"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"


class IntelligenceType(StrEnum):
    HOTSPOT = "HOTSPOT"
    TREND_ALERT = "TREND_ALERT"
    MO_PROFILE = "MO_PROFILE"
    MO_SIMILARITY = "MO_SIMILARITY"
    ASSOCIATION = "ASSOCIATION"
    IDENTITY_CANDIDATE = "IDENTITY_CANDIDATE"
    ANOMALY = "ANOMALY"
    AREA_RISK = "AREA_RISK"


#: Types whose results are area/window aggregates with no single backing case
#: list. emit() accepts an empty evidence_case_ids ONLY for these (documented
#: whitelist — issue #24 SDK enforcement rule). AREA_RISK scores whole areas
#: (ADR-005); every other type must cite the cases behind each result.
AGGREGATE_ONLY_TYPES = frozenset({IntelligenceType.AREA_RISK})


class RunStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


#: Serialization cap for huge evidence lists — the full list is always stored
#: and retrievable; previews show the first N with an "and N more" remainder.
EVIDENCE_PREVIEW_CAP = 25


class Factor(BaseModel):
    """One explanatory factor behind a result: name, contribution, direction."""

    model_config = ConfigDict(frozen=True)

    name: str
    contribution: float
    direction: Literal["UP", "DOWN", "NEUTRAL"] = "UP"


class IntelligenceRun(BaseModel):
    """One analytics execution: type, method+version, window, scope, status."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    intelligence_type: IntelligenceType
    method_name: str
    method_version: str
    model_version: str | None = None
    analysis_window_from: datetime
    analysis_window_to: datetime
    scope_district_id: int | None = None
    scope_unit_id: int | None = None
    status: RunStatus = RunStatus.RUNNING
    error: str | None = None
    generated_at: datetime
    record_count: int = 0


class IntelligenceEvidence(BaseModel):
    """Evidence for one result of a run — classification is mandatory."""

    model_config = ConfigDict(frozen=True)

    evidence_id: int | None = None  # assigned by the store
    run_id: str
    result_ref: str
    evidence_case_ids: tuple[int, ...] = ()  # CaseMaster.CaseMasterID (OBSERVED)
    factors: tuple[Factor, ...] = ()
    limitations: tuple[str, ...] = ()
    classification: DataClassification = Field(...)  # no default — always explicit

    def evidence_preview(self) -> tuple[tuple[int, ...], int]:
        """First EVIDENCE_PREVIEW_CAP case IDs + count of the remainder."""
        head = self.evidence_case_ids[:EVIDENCE_PREVIEW_CAP]
        return head, len(self.evidence_case_ids) - len(head)
