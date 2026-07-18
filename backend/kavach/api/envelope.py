"""Data classification envelope for API responses (PROV-002/#25, ADR-009).

Every intelligence payload group carries: machine-readable classification
(six-class enum from the provenance core), a centralized human label
(single source — i18n-ready), method/model versions, and an evidence
pointer into IntelligenceRun/IntelligenceEvidence (#24). The UI renders
these 1:1 as badges (UI-001); nothing user-facing invents its own strings.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from kavach.provenance import DataClassification

#: Centralized human-readable strings — the ONLY place display text for
#: classifications lives (i18n swaps this table, not call sites).
CLASSIFICATION_LABELS: dict[DataClassification, str] = {
    DataClassification.FACT: "Observed fact",
    DataClassification.DERIVED_METRIC: "Derived metric",
    DataClassification.STATISTICAL_INFERENCE: "Statistical inference",
    DataClassification.AI_DERIVED: "AI-derived",
    DataClassification.POTENTIAL_ASSOCIATION: "Potential association — unconfirmed",
    DataClassification.HUMAN_CONFIRMED: "Human-confirmed",
}


class MethodInfo(BaseModel):
    """Provenance of the computation that produced a payload."""

    model_config = ConfigDict(frozen=True)

    method_name: str
    method_version: str
    model_version: str | None = None


class EvidenceRef(BaseModel):
    """Pointer into the provenance store (#24): run → result → cases."""

    model_config = ConfigDict(frozen=True)

    run_id: str | None = None
    result_ref: str | None = None
    evidence_case_ids: tuple[int, ...] = ()


class IntelligenceEnvelope(BaseModel):
    """Response-level classification block carried by every analytics payload."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "classification": "FACT",
                    "classification_label": "Observed fact",
                    "method": {"method_name": "source_restatement", "method_version": "1.0.0"},
                },
                {
                    "classification": "DERIVED_METRIC",
                    "classification_label": "Derived metric",
                    "method": {
                        "method_name": "district_window_aggregation",
                        "method_version": "1.0.0",
                    },
                },
                {
                    "classification": "STATISTICAL_INFERENCE",
                    "classification_label": "Statistical inference",
                    "method": {"method_name": "dbscan_haversine", "method_version": "1.0.0"},
                    "evidence": {"run_id": "3f2a…", "result_ref": "hotspot:1"},
                },
                {
                    "classification": "AI_DERIVED",
                    "classification_label": "AI-derived",
                    "method": {
                        "method_name": "mo_extraction",
                        "method_version": "1.0.0",
                        "model_version": "claude-sonnet-5",
                    },
                },
                {
                    "classification": "POTENTIAL_ASSOCIATION",
                    "classification_label": "Potential association — unconfirmed",
                    "method": {"method_name": "mo_similarity", "method_version": "1.0.0"},
                },
                {
                    "classification": "HUMAN_CONFIRMED",
                    "classification_label": "Human-confirmed",
                    "method": {"method_name": "identity_review", "method_version": "1.0.0"},
                },
            ]
        },
    )

    classification: DataClassification
    classification_label: str = ""  # filled from CLASSIFICATION_LABELS
    method: MethodInfo
    evidence: EvidenceRef | None = None
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _fill_label_and_guard(self) -> IntelligenceEnvelope:
        object.__setattr__(
            self, "classification_label", CLASSIFICATION_LABELS[self.classification]
        )
        # Boundary rule 3: AI_DERIVED always carries a model version.
        if self.classification is DataClassification.AI_DERIVED and not self.method.model_version:
            raise ValueError("AI_DERIVED payloads must carry method.model_version")
        return self


class ClassifiedValue(BaseModel):
    """One field-group value with its own classification (finer-grained than
    the response envelope; used when a payload mixes classifications)."""

    model_config = ConfigDict(frozen=True)

    value: Any
    classification: DataClassification
    classification_label: str = ""
    confidence: float | None = None
    method: MethodInfo | None = None
    evidence: EvidenceRef | None = None

    @model_validator(mode="after")
    def _fill_label_and_guard(self) -> ClassifiedValue:
        object.__setattr__(
            self, "classification_label", CLASSIFICATION_LABELS[self.classification]
        )
        # Boundary rule 3: AI_DERIVED values always carry confidence + model version.
        if self.classification is DataClassification.AI_DERIVED:
            if self.confidence is None:
                raise ValueError("AI_DERIVED values must carry confidence")
            if self.method is None or not self.method.model_version:
                raise ValueError("AI_DERIVED values must carry method.model_version")
        return self


class ClassificationInfo(BaseModel):
    """One row of the classification legend served to the UI (badge map)."""

    model_config = ConfigDict(frozen=True)

    classification: DataClassification
    label: str


def classification_legend() -> list[ClassificationInfo]:
    """All six classes with their centralized labels — UI badges map 1:1."""
    return [
        ClassificationInfo(classification=c, label=CLASSIFICATION_LABELS[c])
        for c in DataClassification
    ]


def envelope(
    *,
    classification: DataClassification,
    method_name: str,
    method_version: str,
    model_version: str | None = None,
    run_id: str | None = None,
    result_ref: str | None = None,
    evidence_case_ids: tuple[int, ...] = (),
    limitations: tuple[str, ...] = (),
) -> dict:
    """Serializer helper: build the response-level envelope as a plain dict."""
    ev = None
    if run_id or result_ref or evidence_case_ids:
        ev = EvidenceRef(
            run_id=run_id, result_ref=result_ref, evidence_case_ids=evidence_case_ids
        )
    return IntelligenceEnvelope(
        classification=classification,
        method=MethodInfo(
            method_name=method_name, method_version=method_version, model_version=model_version
        ),
        evidence=ev,
        limitations=limitations,
    ).model_dump(exclude_none=True)
