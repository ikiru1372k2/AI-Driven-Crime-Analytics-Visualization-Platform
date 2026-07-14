"""ArrestSurrender repository (matrix §1.6).

Cross-jurisdiction arrest signals (state/district of arrest vs case
registration) feed entity resolution (#48 geography-overlap features) and the
association graph (#45 ARRESTED_IN / PRODUCED_AT edges).
"""

import sqlite3
from datetime import date

from kavach.domain.arrest import ArrestSurrender

_COLS = {
    "ArrestSurrenderID": "arrest_surrender_id",
    "CaseMasterID": "case_master_id",
    "ArrestSurrenderTypeID": "arrest_surrender_type_id",
    "ArrestSurrenderDate": "arrest_surrender_date",
    "ArrestSurrenderStateId": "arrest_surrender_state_id",
    "ArrestSurrenderDistrictId": "arrest_surrender_district_id",
    "PoliceStationID": "police_station_id",
    "IOID": "ioid",
    "CourtID": "court_id",
    "AccusedMasterID": "accused_master_id",
    "IsAccused": "is_accused",
    "IsComplainantAccused": "is_complainant_accused",
}
_BOOLS = {"is_accused", "is_complainant_accused"}


def _row_to_entity(r: sqlite3.Row) -> ArrestSurrender:
    data = {dom: r[db] for db, dom in _COLS.items()}
    for f in _BOOLS:
        if data[f] is not None:
            data[f] = bool(data[f])
    return ArrestSurrender(**data)


class ArrestRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def insert(self, a: ArrestSurrender) -> None:
        cols = list(_COLS)
        vals = []
        for c in cols:
            v = getattr(a, _COLS[c])
            if isinstance(v, bool):
                v = int(v)
            elif isinstance(v, date):
                v = v.isoformat()
            vals.append(v)
        self._conn.execute(
            f"INSERT INTO ArrestSurrender ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            vals,
        )

    def for_case(self, case_master_id: int) -> list[ArrestSurrender]:
        rows = self._conn.execute(
            "SELECT * FROM ArrestSurrender WHERE CaseMasterID = ? ORDER BY ArrestSurrenderID",
            (case_master_id,),
        ).fetchall()
        return [_row_to_entity(r) for r in rows]

    def for_accused_record(self, accused_master_id: int) -> list[ArrestSurrender]:
        """Arrests for one per-case accused record (AccusedMasterID — a
        per-case key, so this is NOT a cross-case identity query; ADR-003)."""
        rows = self._conn.execute(
            "SELECT * FROM ArrestSurrender WHERE AccusedMasterID = ? ORDER BY ArrestSurrenderID",
            (accused_master_id,),
        ).fetchall()
        return [_row_to_entity(r) for r in rows]

    def arrest_districts_for_cases(self, case_ids: list[int]) -> dict[int, set[int]]:
        """Batched: case -> set of arrest districts (single query, no N+1)."""
        if not case_ids:
            return {}
        ph = ", ".join("?" * len(case_ids))
        rows = self._conn.execute(
            f"SELECT CaseMasterID, ArrestSurrenderDistrictId FROM ArrestSurrender "
            f"WHERE CaseMasterID IN ({ph}) AND ArrestSurrenderDistrictId IS NOT NULL",  # noqa: S608
            case_ids,
        ).fetchall()
        out: dict[int, set[int]] = {}
        for r in rows:
            out.setdefault(r["CaseMasterID"], set()).add(r["ArrestSurrenderDistrictId"])
        return out
