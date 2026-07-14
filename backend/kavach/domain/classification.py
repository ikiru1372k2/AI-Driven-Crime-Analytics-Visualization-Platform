"""Legal & crime-classification lookup entities — exact ER mappings.

Source: docs/schema/er-conformance-matrix.md §1.7–§1.11, §1.15, §1.24, §1.25.

Documented quirks handled here:
- Q4: Section / CrimeHeadActSection have no documented PK — implied composite
  keys (ActCode, SectionCode) / (CrimeHeadID, ActCode, SectionCode);
  uniqueness is enforced at ingestion validation only (DATA-002).
- Q5: CrimeSubHead.CrimeHeadName holds the *sub-head* name — mapped to the
  domain field `crime_sub_head_name` (mapping documented in
  docs/schema/field-mappings/classification.md).
"""

from pydantic import BaseModel, ConfigDict


class Act(BaseModel):
    model_config = ConfigDict(frozen=True)

    act_code: str  # PK (VARCHAR)
    act_description: str | None = None
    short_name: str | None = None
    active: bool | None = None


class Section(BaseModel):
    model_config = ConfigDict(frozen=True)

    act_code: str  # FK Act.ActCode; composite identity with section_code (Q4)
    section_code: str
    section_description: str | None = None
    active: bool | None = None


class CrimeHeadActSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    crime_head_id: int  # FK CrimeHead
    act_code: str  # FK Act
    section_code: str


class CrimeHead(BaseModel):
    model_config = ConfigDict(frozen=True)

    crime_head_id: int  # PK
    crime_group_name: str | None = None
    active: bool | None = None


class CrimeSubHead(BaseModel):
    model_config = ConfigDict(frozen=True)

    crime_sub_head_id: int  # PK
    crime_head_id: int | None = None  # FK CrimeHead
    crime_sub_head_name: str | None = None  # DB column: CrimeHeadName (Q5)
    seq_id: int | None = None


class CaseCategory(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_category_id: int  # PK
    lookup_value: str | None = None  # FIR, UDR, PAR, ...


class GravityOffence(BaseModel):
    model_config = ConfigDict(frozen=True)

    gravity_offence_id: int  # PK
    lookup_value: str | None = None  # Heinous / Non-Heinous


class CaseStatusMaster(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_status_id: int  # PK
    case_status_name: str | None = None


class CaseClassification(BaseModel):
    """Resolved display names for a CaseMaster's classification FKs.

    Unresolvable (dangling) FKs stay None — surfaced, never invented.
    """

    model_config = ConfigDict(frozen=True)

    case_category: str | None = None
    gravity_offence: str | None = None
    crime_major_head: str | None = None
    crime_minor_head: str | None = None
    case_status: str | None = None
