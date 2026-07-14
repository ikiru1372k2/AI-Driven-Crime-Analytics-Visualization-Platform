"""ER-003 (#8): round-trips + semantic guard tests (ADR-003 / ADR-009 / Q2)."""

import inspect
import re

from kavach.domain.persons import (
    PROHIBITED_ANALYTICS_FIELDS,
    Accused,
    AccusedAnalyticsView,
    ComplainantAnalyticsView,
    ComplainantDetails,
    Victim,
    normalize_gender_code,
)
from kavach.repositories import person_repository
from kavach.repositories.dev_fixture import connect
from kavach.repositories.person_repository import (
    _ACCUSED_COLS,
    _COMPLAINANT_COLS,
    _VICTIM_COLS,
    PersonRepository,
)


def repo() -> PersonRepository:
    return PersonRepository(connect())


ACC = Accused(
    accused_master_id=101, case_master_id=5501, accused_name="Ravi Kumar",
    age_year=29, gender_id="M", person_id="A1",
)
VIC = Victim(
    victim_master_id=201, case_master_id=5501, victim_name="Test Victim",
    age_year=54, gender_id="f", victim_police="0",
)
COM = ComplainantDetails(
    complainant_id=301, case_master_id=5501, complainant_name="Test Complainant",
    age_year=41, occupation_id=3, religion_id=1, caste_id=7, gender_id="F",
)


def test_roundtrips_preserve_all_documented_fields():
    r = repo()
    r.insert_accused(ACC)
    r.insert_victim(VIC)
    r.insert_complainant(COM)
    assert r.accused_for_case(5501) == [ACC]
    assert r.victims_for_case(5501) == [VIC]
    assert r.complainants_for_case(5501) == [COM]


def test_victim_police_quirk_q2_defensive_parse():
    assert Victim(victim_master_id=1, case_master_id=1, victim_police="1").is_police_victim is True
    assert VIC.is_police_victim is False
    weird = Victim(victim_master_id=2, case_master_id=1, victim_police="yes")
    assert weird.is_police_victim is None  # preserved verbatim, flagged unknown
    assert weird.victim_police == "yes"


def test_gender_normalization_is_derived_only():
    assert normalize_gender_code("m") == "M"
    assert normalize_gender_code("F") == "F"
    assert normalize_gender_code(None) is None
    # raw value untouched on the entity
    assert VIC.gender_id == "f"


def test_analytics_views_exclude_names():
    r = repo()
    r.insert_accused(ACC)
    r.insert_victim(VIC)
    r.insert_complainant(COM)
    for view in (
        r.accused_analytics_views()[0],
        r.victim_analytics_views()[0],
        r.complainant_analytics_views()[0],
    ):
        assert not any("name" in f for f in type(view).model_fields)


def test_complainant_analytics_view_excludes_demographics_adr009():
    fields = set(ComplainantAnalyticsView.model_fields)
    assert fields.isdisjoint(PROHIBITED_ANALYTICS_FIELDS)
    assert "religion_id" not in fields and "caste_id" not in fields


def test_accused_view_keeps_person_id_as_ordering_only():
    # person_id present (needed for per-case display order) but documented as
    # ordering; the cross-case-join guard is the source-scan test below.
    assert "person_id" in AccusedAnalyticsView.model_fields


def test_no_cross_case_personid_join_in_repository_source_adr003():
    """Static guard: no SQL in person/case repositories joins or groups on
    PersonID across cases (ADR-003). A violation looks like 'PersonID =' in a
    JOIN/WHERE that isn't scoped to a single CaseMasterID, or GROUP BY PersonID.
    """
    src = inspect.getsource(person_repository)
    assert not re.search(r"GROUP BY\s+PersonID", src, re.I)
    assert not re.search(r"JOIN\s+\w+\s+ON\s+[^\n]*PersonID", src, re.I)


def test_physical_columns_match_documented_er_names():
    conn = connect()
    PersonRepository(conn)
    for table, mapping in (
        ("Accused", _ACCUSED_COLS),
        ("Victim", _VICTIM_COLS),
        ("ComplainantDetails", _COMPLAINANT_COLS),
    ):
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        assert cols == set(mapping), f"{table} drifted from documented schema"
