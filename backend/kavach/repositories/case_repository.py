"""Case-core repository over the dev fixture (Catalyst Data Store backend lands
with CAT-002/#16 behind this same interface).

Field mapping (documented in docs/schema/field-mappings/case.md): physical
columns keep exact ER names; domain entities are snake_case. Values are stored
verbatim — no silent normalization (DATA-002 contract).
"""

import sqlite3
from datetime import date, datetime

from kavach.domain.case import ActSectionAssociation, CaseMaster, ChargesheetDetails

_CASE_COLS = {
    "CaseMasterID": "case_master_id",
    "CrimeNo": "crime_no",
    "CaseNo": "case_no",
    "CrimeRegisteredDate": "crime_registered_date",
    "PolicePersonID": "police_person_id",
    "PoliceStationID": "police_station_id",
    "CaseCategoryID": "case_category_id",
    "GravityOffenceID": "gravity_offence_id",
    "CrimeMajorHeadID": "crime_major_head_id",
    "CrimeMinorHeadID": "crime_minor_head_id",
    "CaseStatusID": "case_status_id",
    "CourtID": "court_id",
    "IncidentFromDate": "incident_from_date",
    "IncidentToDate": "incident_to_date",
    "InfoReceivedPSDate": "info_received_ps_date",
    "latitude": "latitude",
    "longitude": "longitude",
    "BriefFacts": "brief_facts",
}
_ASSOC_COLS = {
    "CaseMasterID": "case_master_id",
    "ActID": "act_id",
    "SectionID": "section_id",
    "ActOrderID": "act_order_id",
    "SectionOrderID": "section_order_id",
}
_CS_COLS = {
    "CSID": "csid",
    "CaseMasterID": "case_master_id",
    "csdate": "csdate",
    "cstype": "cstype",
    "PolicePersonID": "police_person_id",
}


def _store(v: object) -> object:
    return v.isoformat() if isinstance(v, (datetime, date)) else v


class CaseRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # -- CaseMaster -----------------------------------------------------
    def insert_case(self, case: CaseMaster) -> None:
        cols = list(_CASE_COLS)
        vals = [_store(getattr(case, _CASE_COLS[c])) for c in cols]
        self._conn.execute(
            f"INSERT INTO CaseMaster ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            vals,
        )

    def bulk_insert_cases(self, cases: list[CaseMaster]) -> None:
        for c in cases:
            self.insert_case(c)

    def get_case(self, case_master_id: int) -> CaseMaster | None:
        row = self._conn.execute(
            "SELECT * FROM CaseMaster WHERE CaseMasterID = ?", (case_master_id,)
        ).fetchone()
        if row is None:
            return None
        return CaseMaster(**{dom: row[db] for db, dom in _CASE_COLS.items()})

    def list_window(self, start: datetime, end: datetime) -> list[CaseMaster]:
        """Cases whose occurrence time (IncidentFromDate — never
        CrimeRegisteredDate) falls in [start, end)."""
        rows = self._conn.execute(
            "SELECT * FROM CaseMaster WHERE IncidentFromDate >= ? AND IncidentFromDate < ? "
            "ORDER BY IncidentFromDate",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [CaseMaster(**{dom: r[db] for db, dom in _CASE_COLS.items()}) for r in rows]

    # -- ActSectionAssociation -----------------------------------------
    def insert_association(self, assoc: ActSectionAssociation) -> None:
        cols = list(_ASSOC_COLS)
        self._conn.execute(
            f"INSERT INTO ActSectionAssociation ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [getattr(assoc, _ASSOC_COLS[c]) for c in cols],
        )

    def list_associations(self, case_master_id: int) -> list[ActSectionAssociation]:
        rows = self._conn.execute(
            "SELECT * FROM ActSectionAssociation WHERE CaseMasterID = ? "
            "ORDER BY ActOrderID, SectionOrderID",
            (case_master_id,),
        ).fetchall()
        return [
            ActSectionAssociation(**{dom: r[db] for db, dom in _ASSOC_COLS.items()}) for r in rows
        ]

    # -- ChargesheetDetails ---------------------------------------------
    def insert_chargesheet(self, cs: ChargesheetDetails) -> None:
        cols = list(_CS_COLS)
        self._conn.execute(
            f"INSERT INTO ChargesheetDetails ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [_store(getattr(cs, _CS_COLS[c])) for c in cols],
        )

    def list_chargesheets(self, case_master_id: int) -> list[ChargesheetDetails]:
        rows = self._conn.execute(
            "SELECT * FROM ChargesheetDetails WHERE CaseMasterID = ? ORDER BY CSID",
            (case_master_id,),
        ).fetchall()
        return [ChargesheetDetails(**{dom: r[db] for db, dom in _CS_COLS.items()}) for r in rows]
