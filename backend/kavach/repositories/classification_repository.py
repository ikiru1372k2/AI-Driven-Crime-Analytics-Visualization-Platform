"""Classification lookup repository + resolver.

Physical columns preserve exact documented ER names (matrix §1.7–1.11, §1.15,
§1.24, §1.25). Q3 handling: ActSectionAssociation.ActID/SectionID are INT in
the source document while Act.ActCode/Section.SectionCode are VARCHAR — joins
are performed by string value (documented in field-mappings/classification.md).
Q5 handling: CrimeSubHead.CrimeHeadName -> domain `crime_sub_head_name`.

Lookups are loaded once per repository instance (small reference tables) so
per-case resolution is O(1) dict access — no query-in-loop / N+1 patterns.
"""

import sqlite3

from kavach.domain.case import CaseMaster
from kavach.domain.classification import (
    Act,
    CaseCategory,
    CaseClassification,
    CaseStatusMaster,
    CrimeHead,
    CrimeHeadActSection,
    CrimeSubHead,
    GravityOffence,
    Section,
)

_TABLES: dict[str, dict[str, str]] = {
    "Act": {
        "ActCode": "act_code",
        "ActDescription": "act_description",
        "ShortName": "short_name",
        "Active": "active",
    },
    "Section": {
        "ActCode": "act_code",
        "SectionCode": "section_code",
        "SectionDescription": "section_description",
        "Active": "active",
    },
    "CrimeHeadActSection": {
        "CrimeHeadID": "crime_head_id",
        "ActCode": "act_code",
        "SectionCode": "section_code",
    },
    "CrimeHead": {
        "CrimeHeadID": "crime_head_id",
        "CrimeGroupName": "crime_group_name",
        "Active": "active",
    },
    "CrimeSubHead": {
        "CrimeSubHeadID": "crime_sub_head_id",
        "CrimeHeadID": "crime_head_id",
        "CrimeHeadName": "crime_sub_head_name",  # Q5
        "SeqID": "seq_id",
    },
    "CaseCategory": {"CaseCategoryID": "case_category_id", "LookupValue": "lookup_value"},
    "GravityOffence": {"GravityOffenceID": "gravity_offence_id", "LookupValue": "lookup_value"},
    "CaseStatusMaster": {"CaseStatusID": "case_status_id", "CaseStatusName": "case_status_name"},
}

_MODELS = {
    "Act": Act,
    "Section": Section,
    "CrimeHeadActSection": CrimeHeadActSection,
    "CrimeHead": CrimeHead,
    "CrimeSubHead": CrimeSubHead,
    "CaseCategory": CaseCategory,
    "GravityOffence": GravityOffence,
    "CaseStatusMaster": CaseStatusMaster,
}


class ClassificationRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def insert(self, entity) -> None:
        table = type(entity).__name__
        mapping = _TABLES[table]
        cols = list(mapping)
        self._conn.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            [getattr(entity, mapping[c]) for c in cols],
        )

    def list_all(self, table: str) -> list:
        mapping, model = _TABLES[table], _MODELS[table]
        rows = self._conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608 — table from fixed map
        out = []
        for r in rows:
            data = {dom: r[db] for db, dom in mapping.items()}
            if "active" in data and data["active"] is not None:
                data["active"] = bool(data["active"])
            out.append(model(**data))
        return out


class ClassificationResolver:
    """Resolves CaseMaster classification FKs and Q3 value-joins to names.

    Reference tables are cached in-process (they are small and stable —
    Catalyst Cache is a documented candidate once CAT-001 verifies it).
    Dangling FKs resolve to None; never invented.
    """

    def __init__(self, repo: ClassificationRepository):
        self._acts = {a.act_code: a for a in repo.list_all("Act")}
        self._sections = {(s.act_code, s.section_code): s for s in repo.list_all("Section")}
        self._heads = {h.crime_head_id: h for h in repo.list_all("CrimeHead")}
        self._subheads = {s.crime_sub_head_id: s for s in repo.list_all("CrimeSubHead")}
        self._categories = {c.case_category_id: c for c in repo.list_all("CaseCategory")}
        self._gravities = {g.gravity_offence_id: g for g in repo.list_all("GravityOffence")}
        self._statuses = {s.case_status_id: s for s in repo.list_all("CaseStatusMaster")}

    def resolve_act(self, act_id: int | str | None) -> Act | None:
        """Q3: ActID (INT in source) joined by string value to ActCode."""
        return None if act_id is None else self._acts.get(str(act_id))

    def resolve_section(
        self, act_id: int | str | None, section_id: int | str | None
    ) -> Section | None:
        if act_id is None or section_id is None:
            return None
        return self._sections.get((str(act_id), str(section_id)))

    def classify_case(self, case: CaseMaster) -> CaseClassification:
        head = self._heads.get(case.crime_major_head_id)
        sub = self._subheads.get(case.crime_minor_head_id)
        cat = self._categories.get(case.case_category_id)
        grav = self._gravities.get(case.gravity_offence_id)
        status = self._statuses.get(case.case_status_id)
        return CaseClassification(
            case_category=cat.lookup_value if cat else None,
            gravity_offence=grav.lookup_value if grav else None,
            crime_major_head=head.crime_group_name if head else None,
            crime_minor_head=sub.crime_sub_head_name if sub else None,
            case_status=status.case_status_name if status else None,
        )

    def subhead_consistent(self, case: CaseMaster) -> bool | None:
        """Flag (not fix) sub-head whose parent differs from the case's major
        head — a documented data-quality signal (ER-004 edge case)."""
        sub = self._subheads.get(case.crime_minor_head_id)
        if sub is None or case.crime_major_head_id is None or sub.crime_head_id is None:
            return None
        return sub.crime_head_id == case.crime_major_head_id
