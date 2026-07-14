"""ER-006 (#11): ArrestSurrender round-trips, joins, batched district lookup."""

from datetime import date

from kavach.domain.arrest import ArrestSurrender
from kavach.repositories.arrest_repository import _COLS, ArrestRepository
from kavach.repositories.dev_fixture import connect

FULL = ArrestSurrender(
    arrest_surrender_id=1, case_master_id=5501, arrest_surrender_type_id=1,
    arrest_surrender_date=date(2026, 3, 10), arrest_surrender_state_id=29,
    arrest_surrender_district_id=12, police_station_id=1201, ioid=901,
    court_id=12, accused_master_id=101, is_accused=True, is_complainant_accused=False,
)


def repo() -> ArrestRepository:
    return ArrestRepository(connect())


def test_roundtrip_all_documented_fields_incl_bit_flags():
    r = repo()
    r.insert(FULL)
    got = r.for_case(5501)[0]
    assert got == FULL
    assert got.is_accused is True and got.is_complainant_accused is False


def test_roundtrip_nulls():
    r = repo()
    sparse = ArrestSurrender(arrest_surrender_id=2, case_master_id=5501)
    r.insert(sparse)
    assert r.for_case(5501)[0] == sparse


def test_for_accused_record_is_per_case_key():
    r = repo()
    r.insert(FULL)
    assert r.for_accused_record(101)[0].arrest_surrender_id == 1
    assert r.for_accused_record(999) == []


def test_batched_arrest_districts_no_n_plus_1():
    r = repo()
    r.insert(FULL)
    r.insert(ArrestSurrender(arrest_surrender_id=3, case_master_id=5502,
                             arrest_surrender_district_id=44))
    r.insert(ArrestSurrender(arrest_surrender_id=4, case_master_id=5502,
                             arrest_surrender_district_id=12))
    out = r.arrest_districts_for_cases([5501, 5502, 5503])
    assert out == {5501: {12}, 5502: {44, 12}}
    assert r.arrest_districts_for_cases([]) == {}


def test_physical_columns_match_documented_er_names():
    conn = connect()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(ArrestSurrender)")}
    assert cols == set(_COLS)


def test_undefined_junction_table_not_created():
    conn = connect()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE name = 'inv_arrestsurrenderaccused'"
    ).fetchone()
    assert row is None  # matrix §2: UNDEFINED_IN_SOURCE — never invented
