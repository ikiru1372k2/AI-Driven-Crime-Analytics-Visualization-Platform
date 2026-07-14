"""Organization/geography repository + Unit hierarchy resolver.

Physical columns preserve exact documented ER names (matrix §1.12–§1.14,
§1.16–§1.23; Q6 snake_case CasteMaster). The hierarchy resolver powers
drill-down (UI-002) and authorization scoping (SEC-001) with cycle-protected
ParentUnit traversal.
"""

import sqlite3
from dataclasses import dataclass

from kavach.domain.organization import (
    CasteMaster,
    Court,
    Designation,
    District,
    Employee,
    EmployeeAnalyticsView,
    OccupationMaster,
    Rank,
    ReligionMaster,
    State,
    Unit,
    UnitType,
)

_TABLES: dict[str, dict[str, str]] = {
    "State": {
        "StateID": "state_id", "StateName": "state_name",
        "NationalityID": "nationality_id", "Active": "active",
    },
    "District": {
        "DistrictID": "district_id", "DistrictName": "district_name",
        "StateID": "state_id", "Active": "active",
    },
    "Court": {
        "CourtID": "court_id", "CourtName": "court_name",
        "DistrictID": "district_id", "StateID": "state_id", "Active": "active",
    },
    "UnitType": {
        "UnitTypeID": "unit_type_id", "UnitTypeName": "unit_type_name",
        "CityDistState": "city_dist_state", "Hierarchy": "hierarchy", "Active": "active",
    },
    "Unit": {
        "UnitID": "unit_id", "UnitName": "unit_name", "TypeID": "type_id",
        "ParentUnit": "parent_unit", "NationalityID": "nationality_id",
        "StateID": "state_id", "DistrictID": "district_id", "Active": "active",
    },
    "Rank": {
        "RankID": "rank_id", "RankName": "rank_name",
        "Hierarchy": "hierarchy", "Active": "active",
    },
    "Designation": {
        "DesignationID": "designation_id", "DesignationName": "designation_name",
        "Active": "active", "SortOrder": "sort_order",
    },
    "Employee": {
        "EmployeeID": "employee_id", "DistrictID": "district_id", "UnitID": "unit_id",
        "RankID": "rank_id", "DesignationID": "designation_id", "KGID": "kgid",
        "FirstName": "first_name", "EmployeeDOB": "employee_dob", "GenderID": "gender_id",
        "BloodGroupID": "blood_group_id", "PhysicallyChallenged": "physically_challenged",
        "AppointmentDate": "appointment_date",
    },
    "CasteMaster": {"caste_master_id": "caste_master_id", "caste_master_name": "caste_master_name"},
    "ReligionMaster": {"ReligionID": "religion_id", "ReligionName": "religion_name"},
    "OccupationMaster": {"OccupationID": "occupation_id", "OccupationName": "occupation_name"},
}

_MODELS = {
    "State": State, "District": District, "Court": Court, "UnitType": UnitType,
    "Unit": Unit, "Rank": Rank, "Designation": Designation, "Employee": Employee,
    "CasteMaster": CasteMaster, "ReligionMaster": ReligionMaster,
    "OccupationMaster": OccupationMaster,
}
_BOOL_FIELDS = {"active", "physically_challenged"}


class OrganizationRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def insert(self, entity) -> None:
        table = type(entity).__name__
        mapping = _TABLES[table]
        cols = list(mapping)
        vals = []
        for c in cols:
            v = getattr(entity, mapping[c])
            vals.append(v.isoformat() if hasattr(v, "isoformat") else v)
        self._conn.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            vals,
        )

    def list_all(self, table: str) -> list:
        mapping, model = _TABLES[table], _MODELS[table]
        rows = self._conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608 — fixed map
        out = []
        for r in rows:
            data = {dom: r[db] for db, dom in mapping.items()}
            for f in _BOOL_FIELDS:
                if f in data and data[f] is not None:
                    data[f] = bool(data[f])
            out.append(model(**data))
        return out

    def employee_analytics_views(self) -> list[EmployeeAnalyticsView]:
        """PII-free projection: no KGID/FirstName/DOB/health fields."""
        rows = self._conn.execute(
            "SELECT EmployeeID, DistrictID, UnitID, RankID, DesignationID FROM Employee"
        ).fetchall()
        return [
            EmployeeAnalyticsView(
                employee_id=r["EmployeeID"], district_id=r["DistrictID"], unit_id=r["UnitID"],
                rank_id=r["RankID"], designation_id=r["DesignationID"],
            )
            for r in rows
        ]


@dataclass(frozen=True)
class UnitScope:
    """Resolved geographic scope for a unit (drill-down / authorization)."""

    unit_id: int
    district_id: int | None
    state_id: int | None
    parent_chain: tuple[int, ...]  # unit ids root-ward, excluding self
    cycle_detected: bool = False


class UnitHierarchyResolver:
    """Cycle-protected ParentUnit traversal; O(U) load, O(depth) resolve.

    A ParentUnit cycle is a data-quality error: it is reported on the scope
    (cycle_detected=True), never infinite-looped and never silently repaired.
    """

    def __init__(self, repo: OrganizationRepository):
        self._units: dict[int, Unit] = {u.unit_id: u for u in repo.list_all("Unit")}
        self._districts: dict[int, District] = {
            d.district_id: d for d in repo.list_all("District")
        }

    def resolve(self, unit_id: int) -> UnitScope | None:
        unit = self._units.get(unit_id)
        if unit is None:
            return None
        chain: list[int] = []
        seen = {unit_id}
        district_id, state_id = unit.district_id, unit.state_id
        current = unit
        cycle = False
        while current.parent_unit is not None:
            parent_id = current.parent_unit
            if parent_id in seen:
                cycle = True
                break
            parent = self._units.get(parent_id)
            if parent is None:
                break  # dangling parent — chain ends, reported by ingestion QA
            chain.append(parent_id)
            seen.add(parent_id)
            # inherit geography from ancestors when the unit lacks it
            district_id = district_id if district_id is not None else parent.district_id
            state_id = state_id if state_id is not None else parent.state_id
            current = parent
        if state_id is None and district_id is not None:
            d = self._districts.get(district_id)
            state_id = d.state_id if d else None
        return UnitScope(
            unit_id=unit_id, district_id=district_id, state_id=state_id,
            parent_chain=tuple(chain), cycle_detected=cycle,
        )

    def units_in_district(self, district_id: int) -> list[int]:
        return [u.unit_id for u in self._units.values() if u.district_id == district_id]
