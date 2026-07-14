"""Person-record domain entities — exact ER mappings with semantic guards.

Source: docs/schema/er-conformance-matrix.md §1.2 (ComplainantDetails),
§1.4 (Victim), §1.5 (Accused). Sensitivity: HIGH — analytics paths must use
the *_analytics_view projections, which exclude names and (for complainants)
the protected demographic FKs.

SEMANTIC GUARDS (enforced by tests in tests/domain/test_person_guards.py):
- ADR-003: Accused.PersonID is a per-case ordering label (A1, A2, ...).
  It is NEVER a state-wide person identity and must never key cross-case
  joins. Cross-FIR identity exists only as EntityResolutionCandidate
  (AI_DERIVED) / ResolvedIdentity (HUMAN_CONFIRMED).
- ADR-009: ComplainantDetails.OccupationID/ReligionID/CasteID are complainant
  attributes. They are excluded from every analytics projection and are
  prohibited as engine features.
"""

from pydantic import BaseModel, ConfigDict

#: Raw gender codes appear in mixed case in source data ("m"/"F"/"t").
#: Normalization lives ONLY in DERIVED views; raw values are preserved.
_GENDER_NORMALIZED = {"m": "M", "f": "F", "t": "T"}


def normalize_gender_code(raw: str | int | None) -> str | None:
    """DERIVED normalization of gender lookup codes; raw value is untouched."""
    if raw is None:
        return None
    s = str(raw).strip()
    return _GENDER_NORMALIZED.get(s.lower(), s.upper() or None)


class Accused(BaseModel):
    """Per-case accused record (matrix §1.5). NOT a person identity."""

    model_config = ConfigDict(frozen=True)

    accused_master_id: int
    case_master_id: int
    accused_name: str | None = None
    age_year: int | None = None
    gender_id: str | None = None  # documented as lookup, values like M/F/T
    person_id: str | None = None  # per-case ordering: A1, A2, ... (ADR-003)


class Victim(BaseModel):
    """Victim record (matrix §1.4)."""

    model_config = ConfigDict(frozen=True)

    victim_master_id: int
    case_master_id: int
    victim_name: str | None = None
    age_year: int | None = None
    gender_id: str | None = None
    victim_police: str | None = None  # Q2: VARCHAR "1"/"0" — preserved verbatim

    @property
    def is_police_victim(self) -> bool | None:
        """Defensive parse of the Q2 string flag; unexpected values -> None."""
        if self.victim_police == "1":
            return True
        if self.victim_police == "0":
            return False
        return None


class ComplainantDetails(BaseModel):
    """Complainant record (matrix §1.2). Demographics are complainant-only."""

    model_config = ConfigDict(frozen=True)

    complainant_id: int
    case_master_id: int
    complainant_name: str | None = None
    age_year: int | None = None
    occupation_id: int | None = None  # FK OccupationMaster — ADR-009 guarded
    religion_id: int | None = None  # FK ReligionMaster — ADR-009 guarded
    caste_id: int | None = None  # FK CasteMaster.caste_master_id — ADR-009 guarded
    gender_id: str | None = None


class AccusedAnalyticsView(BaseModel):
    """Analytics-safe projection: no name (aggregate paths never see PII)."""

    model_config = ConfigDict(frozen=True)

    accused_master_id: int
    case_master_id: int
    age_year: int | None = None
    gender_id: str | None = None
    person_id: str | None = None  # ordering only — cross-case joins prohibited


class VictimAnalyticsView(BaseModel):
    """Analytics-safe projection: no name."""

    model_config = ConfigDict(frozen=True)

    victim_master_id: int
    case_master_id: int
    age_year: int | None = None
    gender_id: str | None = None
    victim_police: str | None = None


class ComplainantAnalyticsView(BaseModel):
    """Analytics-safe projection: no name, NO demographic FKs (ADR-009)."""

    model_config = ConfigDict(frozen=True)

    complainant_id: int
    case_master_id: int
    age_year: int | None = None
    gender_id: str | None = None


#: Fields prohibited as analytics/engine features (ADR-009). Engine feature
#: manifests are scanned against this set (ER-007 / engine validation suites).
PROHIBITED_ANALYTICS_FIELDS = frozenset(
    {"occupation_id", "religion_id", "caste_id", "OccupationID", "ReligionID", "CasteID"}
)
