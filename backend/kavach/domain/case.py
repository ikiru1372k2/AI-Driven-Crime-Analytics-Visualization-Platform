"""Case-core domain entities — exact mappings of the documented FIR ER schema.

Source of truth: docs/schema/er-conformance-matrix.md §1.1, §1.3, §1.26.
Physical column names (Data Store / dev fixture) preserve the documented ER
names exactly; domain fields are snake_case with the mapping documented in
docs/schema/field-mappings/case.md. No column is invented or renamed in
persistence (ER-002 / #7).
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class CaseMaster(BaseModel):
    """One FIR/case record (matrix §1.1). All 18 documented columns."""

    model_config = ConfigDict(frozen=True)

    case_master_id: int
    crime_no: str | None = None
    case_no: str | None = None
    crime_registered_date: date | None = None
    police_person_id: int | None = None  # FK Employee.EmployeeID
    police_station_id: int | None = None  # FK Unit.UnitID
    case_category_id: int | None = None  # FK CaseCategory
    gravity_offence_id: int | None = None  # FK GravityOffence
    crime_major_head_id: int | None = None  # FK CrimeHead
    crime_minor_head_id: int | None = None  # FK CrimeSubHead
    case_status_id: int | None = None  # FK CaseStatusMaster
    court_id: int | None = None  # FK Court
    incident_from_date: datetime | None = None
    incident_to_date: datetime | None = None
    info_received_ps_date: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    brief_facts: str | None = None

    def occurrence_time(self) -> datetime | None:
        """Authoritative occurrence timestamp for temporal analytics.

        Policy (ER conformance, ADR-008 lineage): IncidentFromDate only.
        CrimeRegisteredDate is registration, not occurrence, and must never be
        substituted — callers exclude records returning None.
        """
        return self.incident_from_date


class ActSectionAssociation(BaseModel):
    """Act/section invoked in a case (matrix §1.3; junction, no documented PK).

    Documented quirk Q3: ActID/SectionID are typed INT in the source document
    while their targets (Act.ActCode, Section.SectionCode) are VARCHAR; the
    values are stored verbatim and joined by value at lookup time (ER-004).
    Implied composite identity: (case_master_id, act_id, section_id).
    """

    model_config = ConfigDict(frozen=True)

    case_master_id: int
    act_id: int | None = None
    section_id: int | None = None
    act_order_id: int | None = None
    section_order_id: int | None = None


#: Documented final-report types for ChargesheetDetails.cstype (matrix §1.26).
CSTYPE_MEANINGS = {"A": "Chargesheet", "B": "False Case", "C": "Undetected"}


class ChargesheetDetails(BaseModel):
    """Chargesheet record (matrix §1.26).

    cstype outside the documented A/B/C set is preserved verbatim (never
    coerced) and can be flagged via `cstype_known`.
    """

    model_config = ConfigDict(frozen=True)

    csid: int
    case_master_id: int
    csdate: datetime | None = None
    cstype: str | None = None
    police_person_id: int | None = None  # FK Employee.EmployeeID (source: "employeeMaster")

    @property
    def cstype_known(self) -> bool:
        return self.cstype in CSTYPE_MEANINGS
