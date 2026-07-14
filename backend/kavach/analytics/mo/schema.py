"""MO extraction schema v1 — the validated contract for BriefFacts enrichment.

ADR-006: free-form LLM output never becomes analytical truth. Every extraction
(QuickML LLM or rule-based fallback, MO-002/#40) is validated against this
schema before persistence; invalid output is rejected whole — never partially
trusted. UNKNOWN is a first-class value and is always preferred over invention.

Source input: CaseMaster.BriefFacts ONLY (OBSERVED). Output classification:
AI_DERIVED (docs/schema/derived-intelligence-schema.md).

Versioning: additive changes only; bump SCHEMA_VERSION and keep validators for
prior majors if stored profiles must remain readable.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "mo-schema-v1"

UNKNOWN = "UNKNOWN"

MOBILITY = ("on_foot", "motorcycle", "car", "autorickshaw", "bicycle",
            "public_transport", "other", UNKNOWN)
APPROACH = ("mobile_approach", "stationary_ambush", "entry_breakin", "deception",
            "confrontation", "other", UNKNOWN)
ACTION = ("snatching", "theft", "burglary", "robbery", "assault", "threat",
          "fraud", "other", UNKNOWN)
TARGET = ("gold_chain", "mobile_phone", "cash", "vehicle", "jewelry", "property",
          "person", "other", UNKNOWN)
TIME_CONTEXT = ("night", "day", "dawn_dusk", UNKNOWN)
WEAPON = ("yes", "no", UNKNOWN)

#: Attributes used for MO similarity (MO-004/#41). escape_direction is
#: display-only and intentionally excluded.
SIMILARITY_ATTRIBUTES = ("offender_count", "mobility", "approach_method",
                         "crime_action", "target_type", "time_context",
                         "weapon_involved")


class MoAttribute(BaseModel):
    """One extracted attribute: value + confidence + optional source span."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: str | int
    confidence: float = Field(ge=0.0, le=1.0)
    source_span: tuple[int, int] | None = None  # [start, end) into BriefFacts

    @field_validator("source_span")
    @classmethod
    def _span_ordered(cls, v):
        if v is not None and v[0] >= v[1]:
            raise ValueError("source_span must be [start, end) with start < end")
        return v


def _vocab_validator(allowed: tuple[str, ...]):
    def check(attr: MoAttribute) -> MoAttribute:
        if attr.value not in allowed:
            raise ValueError(f"value {attr.value!r} not in vocabulary {allowed}")
        return attr

    return check


class MoProfile(BaseModel):
    """Validated structured MO extracted from one case's BriefFacts.

    `extra=forbid` rejects any attribute the schema does not define — an LLM
    inventing fields fails validation instead of polluting analytics.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_master_id: int
    schema_version: Literal["mo-schema-v1"] = SCHEMA_VERSION
    extractor: Literal["QUICKML_LLM", "RULE_BASED"]
    model_version: str
    extracted_at: str  # ISO timestamp, set by the extraction service

    offender_count: MoAttribute  # int >= 1 or UNKNOWN
    mobility: MoAttribute
    approach_method: MoAttribute
    crime_action: MoAttribute
    target_type: MoAttribute
    escape_direction: MoAttribute  # free-text or UNKNOWN; display-only
    time_context: MoAttribute
    weapon_involved: MoAttribute

    @field_validator("offender_count")
    @classmethod
    def _offender_count_valid(cls, attr: MoAttribute) -> MoAttribute:
        v = attr.value
        if v == UNKNOWN:
            return attr
        if isinstance(v, int) and 1 <= v <= 100:
            return attr
        raise ValueError("offender_count must be int in [1,100] or UNKNOWN")

    _mobility = field_validator("mobility")(_vocab_validator(MOBILITY))
    _approach = field_validator("approach_method")(_vocab_validator(APPROACH))
    _action = field_validator("crime_action")(_vocab_validator(ACTION))
    _target = field_validator("target_type")(_vocab_validator(TARGET))
    _time = field_validator("time_context")(_vocab_validator(TIME_CONTEXT))
    _weapon = field_validator("weapon_involved")(_vocab_validator(WEAPON))

    @field_validator("escape_direction")
    @classmethod
    def _escape_free_text(cls, attr: MoAttribute) -> MoAttribute:
        if not isinstance(attr.value, str) or not attr.value.strip():
            raise ValueError("escape_direction must be non-empty text or UNKNOWN")
        return attr

    def known_similarity_attributes(self) -> dict[str, MoAttribute]:
        """Attributes usable for similarity: value != UNKNOWN, excludes
        escape_direction by construction (SIMILARITY_ATTRIBUTES)."""
        out = {}
        for name in SIMILARITY_ATTRIBUTES:
            attr: MoAttribute = getattr(self, name)
            if attr.value != UNKNOWN:
                out[name] = attr
        return out


class MoValidationError(ValueError):
    """Raised when raw extractor output fails schema validation. The offending
    payload is never persisted (whole-rejection, ADR-006)."""


def validate_extraction(raw: dict) -> MoProfile:
    """Validate raw extractor output (parsed JSON) into a MoProfile.

    Raises MoValidationError with a compact reason on ANY violation —
    unknown attributes, out-of-vocabulary values, bad confidences, missing
    fields. Callers must treat failure as EXTRACTION_FAILED (MO-002).
    """
    try:
        return MoProfile.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError and friends
        raise MoValidationError(str(exc)) from exc
