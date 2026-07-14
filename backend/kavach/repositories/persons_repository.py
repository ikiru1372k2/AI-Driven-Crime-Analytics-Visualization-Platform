"""Person-record repository (ER-003 / #8).

HIGH-sensitivity tables. Full entities (with names) are retrievable only via
per-case detail queries; aggregate/analytics paths use the *_analytics_view
projections which exclude names and (for complainants) the ADR-009-protected
demographic FKs. No query in this module keys on Accused.PersonID across
cases (ADR-003 — enforced by tests/domain/test_person_guards.py).
"""

import sqlite3

from kavach.domain.persons import (
    Accused,
    AccusedAnalyticsView,
    ComplainantAnalyticsView,
    ComplainantDetails,
    Victim,
    VictimAnalyticsView,
)

_ACCUSED_COLS = {
    "AccusedMasterID": "accused_master_id",
    "CaseMasterID": "case_master_id",
    "AccusedName": "accused_name",
    "AgeYear": "age_year",
    "GenderID": "gender_id",
    "PersonID": "person_id",
}
_VICTIM_COLS = {
    "VictimMasterID": "victim_master_id",
    "CaseMasterID": "case_master_id",
    "VictimName": "victim_name",
    "AgeYear": "age_year",
    "GenderID": "gender_id",
    "VictimPolice": "victim_police",
}
_COMPLAINANT_COLS = {
    "ComplainantID": "complainant_id",
    "CaseMasterID": "case_master_id",
    "ComplainantName": "complainant_name",
    "AgeYear": "age_year",
    "OccupationID": "occupation_id",
    "ReligionID": "religion_id",
    "CasteID": "caste_id",
    "GenderID": "gender_id",
}


def _insert(conn: sqlite3.Connection, table: str, cols: dict, entity) -> None:
    names = list(cols)
    conn.execute(
        f"INSERT INTO {table} ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})",
        [getattr(entity, cols[c]) for c in names],
    )


class PersonsRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # -- writes ----------------------------------------------------------
    def insert_accused(self, a: Accused) -> None:
        _insert(self._conn, "Accused", _ACCUSED_COLS, a)

    def insert_victim(self, v: Victim) -> None:
        _insert(self._conn, "Victim", _VICTIM_COLS, v)

    def insert_complainant(self, c: ComplainantDetails) -> None:
        _insert(self._conn, "ComplainantDetails", _COMPLAINANT_COLS, c)

    # -- case-detail reads (full entities, scoped access audited upstream) --
    def accused_for_case(self, case_master_id: int) -> list[Accused]:
        rows = self._conn.execute(
            "SELECT * FROM Accused WHERE CaseMasterID = ? ORDER BY AccusedMasterID",
            (case_master_id,),
        ).fetchall()
        return [Accused(**{d: r[c] for c, d in _ACCUSED_COLS.items()}) for r in rows]

    def victims_for_case(self, case_master_id: int) -> list[Victim]:
        rows = self._conn.execute(
            "SELECT * FROM Victim WHERE CaseMasterID = ? ORDER BY VictimMasterID",
            (case_master_id,),
        ).fetchall()
        return [Victim(**{d: r[c] for c, d in _VICTIM_COLS.items()}) for r in rows]

    def complainants_for_case(self, case_master_id: int) -> list[ComplainantDetails]:
        rows = self._conn.execute(
            "SELECT * FROM ComplainantDetails WHERE CaseMasterID = ? ORDER BY ComplainantID",
            (case_master_id,),
        ).fetchall()
        return [ComplainantDetails(**{d: r[c] for c, d in _COMPLAINANT_COLS.items()}) for r in rows]

    # -- analytics reads (projections only: no names, no protected FKs) -----
    def accused_analytics(self) -> list[AccusedAnalyticsView]:
        rows = self._conn.execute(
            "SELECT AccusedMasterID, CaseMasterID, AgeYear, GenderID, PersonID "
            "FROM Accused ORDER BY AccusedMasterID"
        ).fetchall()
        return [
            AccusedAnalyticsView(
                accused_master_id=r["AccusedMasterID"],
                case_master_id=r["CaseMasterID"],
                age_year=r["AgeYear"],
                gender_id=r["GenderID"],
                person_id=r["PersonID"],
            )
            for r in rows
        ]

    def victims_analytics(self) -> list[VictimAnalyticsView]:
        rows = self._conn.execute(
            "SELECT VictimMasterID, CaseMasterID, AgeYear, GenderID, VictimPolice "
            "FROM Victim ORDER BY VictimMasterID"
        ).fetchall()
        return [
            VictimAnalyticsView(
                victim_master_id=r["VictimMasterID"],
                case_master_id=r["CaseMasterID"],
                age_year=r["AgeYear"],
                gender_id=r["GenderID"],
                victim_police=r["VictimPolice"],
            )
            for r in rows
        ]

    def complainants_analytics(self) -> list[ComplainantAnalyticsView]:
        rows = self._conn.execute(
            "SELECT ComplainantID, CaseMasterID, AgeYear, GenderID "
            "FROM ComplainantDetails ORDER BY ComplainantID"
        ).fetchall()
        return [
            ComplainantAnalyticsView(
                complainant_id=r["ComplainantID"],
                case_master_id=r["CaseMasterID"],
                age_year=r["AgeYear"],
                gender_id=r["GenderID"],
            )
            for r in rows
        ]
