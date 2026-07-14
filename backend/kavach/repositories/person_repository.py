"""Person-record repository (Accused, Victim, ComplainantDetails).

Physical columns preserve exact documented ER names (matrix §1.2/§1.4/§1.5).
Analytics access goes through *_analytics_views (no names; complainant views
exclude demographic FKs per ADR-009). Full records (with names) are exposed
only via scoped case-detail lookups — callers are responsible for scope
enforcement (SEC-001/#71) and audit (PROV-003/#26).

ADR-003 guard: this repository intentionally provides NO query keyed on
Accused.PersonID across cases; tests assert the guard.
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

_DDL = [
    """CREATE TABLE IF NOT EXISTS Accused (
        AccusedMasterID INTEGER PRIMARY KEY, CaseMasterID INTEGER NOT NULL,
        AccusedName TEXT, AgeYear INTEGER, GenderID TEXT, PersonID TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS Victim (
        VictimMasterID INTEGER PRIMARY KEY, CaseMasterID INTEGER NOT NULL,
        VictimName TEXT, AgeYear INTEGER, GenderID TEXT, VictimPolice TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ComplainantDetails (
        ComplainantID INTEGER PRIMARY KEY, CaseMasterID INTEGER NOT NULL,
        ComplainantName TEXT, AgeYear INTEGER,
        OccupationID INTEGER, ReligionID INTEGER, CasteID INTEGER, GenderID TEXT
    )""",
]


def _insert(conn: sqlite3.Connection, table: str, mapping: dict, entity) -> None:
    cols = list(mapping)
    conn.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [getattr(entity, mapping[c]) for c in cols],
    )


class PersonRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        for ddl in _DDL:
            conn.execute(ddl)

    # -- writes ----------------------------------------------------------
    def insert_accused(self, a: Accused) -> None:
        _insert(self._conn, "Accused", _ACCUSED_COLS, a)

    def insert_victim(self, v: Victim) -> None:
        _insert(self._conn, "Victim", _VICTIM_COLS, v)

    def insert_complainant(self, c: ComplainantDetails) -> None:
        _insert(self._conn, "ComplainantDetails", _COMPLAINANT_COLS, c)

    # -- scoped case-detail reads (full records incl. PII) ----------------
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

    # -- analytics-safe projections (no names; ADR-009 exclusions) --------
    def accused_analytics_views(self) -> list[AccusedAnalyticsView]:
        rows = self._conn.execute(
            "SELECT AccusedMasterID, CaseMasterID, AgeYear, GenderID, PersonID FROM Accused"
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

    def victim_analytics_views(self) -> list[VictimAnalyticsView]:
        rows = self._conn.execute(
            "SELECT VictimMasterID, CaseMasterID, AgeYear, GenderID, VictimPolice FROM Victim"
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

    def complainant_analytics_views(self) -> list[ComplainantAnalyticsView]:
        rows = self._conn.execute(
            "SELECT ComplainantID, CaseMasterID, AgeYear, GenderID FROM ComplainantDetails"
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
