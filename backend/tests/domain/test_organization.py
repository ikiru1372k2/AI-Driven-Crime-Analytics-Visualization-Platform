"""ER-005 (#10): org/geography mappings, hierarchy resolver, PII projections."""

from datetime import date

from kavach.domain.organization import (
    CasteMaster,
    District,
    Employee,
    EmployeeAnalyticsView,
    State,
    Unit,
)
from kavach.repositories.dev_fixture import connect
from kavach.repositories.organization_repository import (
    _TABLES,
    OrganizationRepository,
    UnitHierarchyResolver,
)


def seeded() -> OrganizationRepository:
    r = OrganizationRepository(connect())
    r.insert(State(state_id=29, state_name="Karnataka", active=True))
    r.insert(District(district_id=44, district_name="Bengaluru City", state_id=29, active=True))
    r.insert(District(district_id=12, district_name="Tumakuru", state_id=29, active=True))
    # 3-level chain: station 4430 -> circle 440 -> district office 44
    r.insert(Unit(unit_id=44, unit_name="Bengaluru City Police", district_id=44,
                  state_id=29, active=True))
    r.insert(Unit(unit_id=440, unit_name="Peenya Circle", parent_unit=44,
                  district_id=44, active=True))
    r.insert(Unit(unit_id=4430, unit_name="Peenya PS", parent_unit=440, active=True))
    return r


def test_hierarchy_resolver_three_level_chain_inherits_geography():
    scope = UnitHierarchyResolver(seeded()).resolve(4430)
    assert scope.parent_chain == (440, 44)
    assert scope.district_id == 44  # inherited from Peenya Circle
    assert scope.state_id == 29  # via District.StateID fallback
    assert not scope.cycle_detected


def test_hierarchy_cycle_detected_not_looped():
    r = seeded()
    r.insert(Unit(unit_id=901, unit_name="A", parent_unit=902))
    r.insert(Unit(unit_id=902, unit_name="B", parent_unit=901))
    scope = UnitHierarchyResolver(r).resolve(901)
    assert scope.cycle_detected is True
    assert 902 in scope.parent_chain


def test_dangling_parent_ends_chain():
    r = seeded()
    r.insert(Unit(unit_id=903, unit_name="Orphan", parent_unit=999))
    scope = UnitHierarchyResolver(r).resolve(903)
    assert scope.parent_chain == ()
    assert scope.district_id is None  # not invented


def test_units_in_district():
    resolver = UnitHierarchyResolver(seeded())
    assert set(resolver.units_in_district(44)) == {44, 440}


def test_employee_roundtrip_and_pii_free_projection():
    r = seeded()
    r.insert(Employee(
        employee_id=901, district_id=44, unit_id=4430, rank_id=5, designation_id=2,
        kgid="KGID123", first_name="Officer", employee_dob=date(1985, 5, 1),
        gender_id="M", blood_group_id=3, physically_challenged=False,
        appointment_date=date(2010, 6, 1),
    ))
    full = r.list_all("Employee")[0]
    assert full.kgid == "KGID123" and full.physically_challenged is False
    view = r.employee_analytics_views()[0]
    fields = set(EmployeeAnalyticsView.model_fields)
    assert fields.isdisjoint({"kgid", "first_name", "employee_dob", "blood_group_id",
                              "physically_challenged"})
    assert view.unit_id == 4430


def test_caste_master_snake_case_q6_roundtrip():
    r = seeded()
    r.insert(CasteMaster(caste_master_id=7, caste_master_name="Test Caste"))
    assert r.list_all("CasteMaster")[0].caste_master_name == "Test Caste"
    cols = {row[1] for row in r._conn.execute("PRAGMA table_info(CasteMaster)")}
    assert cols == {"caste_master_id", "caste_master_name"}  # physical snake_case


def test_physical_columns_match_documented_er_names():
    conn = connect()
    for table, mapping in _TABLES.items():
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        assert cols == set(mapping), f"{table} drifted from documented schema"
