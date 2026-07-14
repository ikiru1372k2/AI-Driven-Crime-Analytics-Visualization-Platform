"""Geography, police-organization and demographic lookup entities.

Source: docs/schema/er-conformance-matrix.md §1.12–§1.14 (demographic masters),
§1.16–§1.23 (Court, District, State, Unit, UnitType, Rank, Designation,
Employee).

Quirks handled:
- Q6: CasteMaster uses snake_case physical columns — preserved.
- Q9: NationalityID (State, Unit) has no documented FK target — plain INT.
- Employee PII (KGID, EmployeeDOB) is HIGH sensitivity; analytics paths use
  EmployeeAnalyticsView which excludes them.
- ADR-009: demographic masters resolve ONLY within complainant context.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict


class State(BaseModel):
    model_config = ConfigDict(frozen=True)

    state_id: int  # PK
    state_name: str | None = None
    nationality_id: int | None = None  # Q9: no documented FK target
    active: bool | None = None


class District(BaseModel):
    model_config = ConfigDict(frozen=True)

    district_id: int  # PK
    district_name: str | None = None
    state_id: int | None = None  # FK State
    active: bool | None = None


class Court(BaseModel):
    model_config = ConfigDict(frozen=True)

    court_id: int  # PK
    court_name: str | None = None
    district_id: int | None = None  # FK District
    state_id: int | None = None  # FK State
    active: bool | None = None


class UnitType(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit_type_id: int  # PK
    unit_type_name: str | None = None
    city_dist_state: str | None = None  # operational level: City/District/State
    hierarchy: int | None = None  # lower = higher authority
    active: bool | None = None


class Unit(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit_id: int  # PK
    unit_name: str | None = None
    type_id: int | None = None  # FK UnitType
    parent_unit: int | None = None  # self-reference -> Unit.UnitID
    nationality_id: int | None = None  # Q9
    state_id: int | None = None  # FK State
    district_id: int | None = None  # FK District
    active: bool | None = None


class Rank(BaseModel):
    model_config = ConfigDict(frozen=True)

    rank_id: int  # PK
    rank_name: str | None = None
    hierarchy: int | None = None  # lower = higher rank
    active: bool | None = None


class Designation(BaseModel):
    model_config = ConfigDict(frozen=True)

    designation_id: int  # PK
    designation_name: str | None = None
    active: bool | None = None
    sort_order: int | None = None


class Employee(BaseModel):
    """Police employee (matrix §1.23). KGID/DOB are PII — see analytics view."""

    model_config = ConfigDict(frozen=True)

    employee_id: int  # PK
    district_id: int | None = None
    unit_id: int | None = None
    rank_id: int | None = None
    designation_id: int | None = None
    kgid: str | None = None  # PII
    first_name: str | None = None  # PII
    employee_dob: date | None = None  # PII
    gender_id: str | None = None
    blood_group_id: int | None = None
    physically_challenged: bool | None = None
    appointment_date: date | None = None


class EmployeeAnalyticsView(BaseModel):
    """Analytics-safe projection: no KGID, no DOB, no name, no health fields."""

    model_config = ConfigDict(frozen=True)

    employee_id: int
    district_id: int | None = None
    unit_id: int | None = None
    rank_id: int | None = None
    designation_id: int | None = None


class CasteMaster(BaseModel):
    """Q6: snake_case physical columns preserved. ADR-009: complainant-context only."""

    model_config = ConfigDict(frozen=True)

    caste_master_id: int  # PK (physical: caste_master_id)
    caste_master_name: str | None = None


class ReligionMaster(BaseModel):
    model_config = ConfigDict(frozen=True)

    religion_id: int  # PK
    religion_name: str | None = None


class OccupationMaster(BaseModel):
    model_config = ConfigDict(frozen=True)

    occupation_id: int  # PK
    occupation_name: str | None = None
