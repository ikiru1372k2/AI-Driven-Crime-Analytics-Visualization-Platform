"""ER-002 (#7): round-trip and semantic tests for case-core mappings."""

from datetime import date, datetime

from kavach.domain.case import ActSectionAssociation, CaseMaster, ChargesheetDetails
from kavach.repositories.case_repository import (
    _ASSOC_COLS,
    _CASE_COLS,
    _CS_COLS,
    CaseRepository,
)
from kavach.repositories.dev_fixture import connect

FULL_CASE = CaseMaster(
    case_master_id=5501,
    crime_no="104430006202600001",
    case_no="202600001",
    crime_registered_date=date(2026, 3, 2),
    police_person_id=901,
    police_station_id=4430,
    case_category_id=1,
    gravity_offence_id=2,
    crime_major_head_id=7,
    crime_minor_head_id=71,
    case_status_id=1,
    court_id=12,
    incident_from_date=datetime(2026, 3, 1, 23, 40),
    incident_to_date=datetime(2026, 3, 2, 0, 10),
    info_received_ps_date=datetime(2026, 3, 2, 8, 5),
    latitude=13.0284,
    longitude=77.5232,
    brief_facts="Two unknown persons on a motorcycle snatched a gold chain.",
)


def repo() -> CaseRepository:
    return CaseRepository(connect())


def test_case_roundtrip_all_fields():
    r = repo()
    r.insert_case(FULL_CASE)
    assert r.get_case(5501) == FULL_CASE


def test_case_roundtrip_with_nulls():
    r = repo()
    sparse = CaseMaster(case_master_id=5502)  # every optional field null
    r.insert_case(sparse)
    got = r.get_case(5502)
    assert got == sparse
    assert got.latitude is None and got.incident_from_date is None


def test_occurrence_time_uses_incident_from_date_only():
    assert FULL_CASE.occurrence_time() == datetime(2026, 3, 1, 23, 40)
    # Registration date must never substitute occurrence time (ER conformance).
    registered_only = CaseMaster(case_master_id=1, crime_registered_date=date(2026, 3, 2))
    assert registered_only.occurrence_time() is None


def test_list_window_filters_on_incident_from_date():
    r = repo()
    r.insert_case(FULL_CASE)
    r.insert_case(CaseMaster(case_master_id=5503, incident_from_date=datetime(2026, 4, 1)))
    r.insert_case(CaseMaster(case_master_id=5504))  # no occurrence time -> excluded
    window = r.list_window(datetime(2026, 3, 1), datetime(2026, 3, 31))
    assert [c.case_master_id for c in window] == [5501]


def test_association_roundtrip_composite_identity():
    r = repo()
    a1 = ActSectionAssociation(
        case_master_id=5501, act_id=1, section_id=302, act_order_id=1, section_order_id=1
    )
    a2 = ActSectionAssociation(
        case_master_id=5501, act_id=1, section_id=307, act_order_id=1, section_order_id=2
    )
    r.insert_association(a2)
    r.insert_association(a1)
    assert r.list_associations(5501) == [a1, a2]  # ordered by documented print order


def test_chargesheet_cstype_preserved_verbatim():
    r = repo()
    known = ChargesheetDetails(
        csid=1, case_master_id=5501, csdate=datetime(2026, 6, 1, 10), cstype="A"
    )
    unknown = ChargesheetDetails(csid=2, case_master_id=5501, cstype="Z")
    r.insert_chargesheet(known)
    r.insert_chargesheet(unknown)
    got = r.list_chargesheets(5501)
    assert got[0].cstype_known and got[0].cstype == "A"
    assert not got[1].cstype_known and got[1].cstype == "Z"  # preserved, flagged


def test_physical_columns_match_documented_er_names():
    """No invented/renamed persistence columns (matrix §1.1/§1.3/§1.26)."""
    conn = connect()
    for table, mapping in (
        ("CaseMaster", _CASE_COLS),
        ("ActSectionAssociation", _ASSOC_COLS),
        ("ChargesheetDetails", _CS_COLS),
    ):
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        assert cols == set(mapping), f"{table} drifted from documented schema"
