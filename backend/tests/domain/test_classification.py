"""ER-004 (#9): classification lookups, Q3 value-joins, Q5 mapping, resolver."""

from kavach.domain.case import CaseMaster
from kavach.domain.classification import (
    Act,
    CaseCategory,
    CaseStatusMaster,
    CrimeHead,
    CrimeSubHead,
    GravityOffence,
    Section,
)
from kavach.repositories.classification_repository import (
    _TABLES,
    ClassificationRepository,
    ClassificationResolver,
)
from kavach.repositories.dev_fixture import connect


def seeded_repo() -> ClassificationRepository:
    r = ClassificationRepository(connect())
    r.insert(Act(act_code="1", act_description="Indian Penal Code", short_name="IPC", active=True))
    r.insert(Section(act_code="1", section_code="302", section_description="Murder", active=True))
    r.insert(Section(act_code="1", section_code="392", section_description="Robbery", active=True))
    r.insert(CrimeHead(crime_head_id=7, crime_group_name="Crimes Against Property", active=True))
    r.insert(CrimeSubHead(crime_sub_head_id=71, crime_head_id=7,
                          crime_sub_head_name="Robbery", seq_id=1))
    r.insert(CrimeSubHead(crime_sub_head_id=99, crime_head_id=3,
                          crime_sub_head_name="Murder", seq_id=1))
    r.insert(CaseCategory(case_category_id=1, lookup_value="FIR"))
    r.insert(GravityOffence(gravity_offence_id=2, lookup_value="Non-Heinous"))
    r.insert(CaseStatusMaster(case_status_id=1, case_status_name="Under Investigation"))
    return r


CASE = CaseMaster(
    case_master_id=5501, case_category_id=1, gravity_offence_id=2,
    crime_major_head_id=7, crime_minor_head_id=71, case_status_id=1,
)


def test_roundtrip_all_lookup_tables():
    r = seeded_repo()
    assert r.list_all("Act")[0].short_name == "IPC"
    assert len(r.list_all("Section")) == 2
    assert r.list_all("CrimeSubHead")[0].crime_sub_head_name == "Robbery"  # Q5


def test_q3_value_join_int_id_to_varchar_code():
    resolver = ClassificationResolver(seeded_repo())
    assert resolver.resolve_act(1).short_name == "IPC"  # INT 1 -> ActCode "1"
    assert resolver.resolve_section(1, 302).section_description == "Murder"
    assert resolver.resolve_act(999) is None  # dangling -> None, never invented


def test_classify_case_resolves_all_names():
    c = ClassificationResolver(seeded_repo()).classify_case(CASE)
    assert c.case_category == "FIR"
    assert c.gravity_offence == "Non-Heinous"
    assert c.crime_major_head == "Crimes Against Property"
    assert c.crime_minor_head == "Robbery"
    assert c.case_status == "Under Investigation"


def test_dangling_fk_resolves_to_none():
    sparse = CaseMaster(case_master_id=1, crime_major_head_id=404)
    c = ClassificationResolver(seeded_repo()).classify_case(sparse)
    assert c.crime_major_head is None and c.case_category is None


def test_subhead_parent_mismatch_flagged_not_fixed():
    resolver = ClassificationResolver(seeded_repo())
    assert resolver.subhead_consistent(CASE) is True
    mismatched = CaseMaster(case_master_id=2, crime_major_head_id=7, crime_minor_head_id=99)
    assert resolver.subhead_consistent(mismatched) is False  # flagged only


def test_duplicate_section_codes_across_acts_are_valid_composite():
    r = seeded_repo()
    r.insert(Act(act_code="NDPS", act_description="NDPS Act", short_name="NDPS", active=True))
    r.insert(Section(act_code="NDPS", section_code="302", section_description="Other", active=True))
    resolver = ClassificationResolver(r)
    assert resolver.resolve_section("NDPS", "302").section_description == "Other"
    assert resolver.resolve_section("1", "302").section_description == "Murder"


def test_physical_columns_match_documented_er_names():
    conn = connect()
    for table, mapping in _TABLES.items():
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        assert cols == set(mapping), f"{table} drifted from documented schema"
