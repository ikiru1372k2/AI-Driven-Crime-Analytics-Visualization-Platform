"""Local SQLite dev fixture (ADR-002).

Development/test stand-in behind the repository interface — NEVER the
submitted store (Catalyst Data Store is primary; provisioning is CAT-002/#16).
Physical column names below reproduce the documented ER names exactly so that
schema-manifest parity checks (ER-007/#12) apply to both backends.
"""

import sqlite3

_DDL = [
    """CREATE TABLE IF NOT EXISTS CaseMaster (
        CaseMasterID INTEGER PRIMARY KEY,
        CrimeNo TEXT, CaseNo TEXT, CrimeRegisteredDate TEXT,
        PolicePersonID INTEGER, PoliceStationID INTEGER, CaseCategoryID INTEGER,
        GravityOffenceID INTEGER, CrimeMajorHeadID INTEGER, CrimeMinorHeadID INTEGER,
        CaseStatusID INTEGER, CourtID INTEGER,
        IncidentFromDate TEXT, IncidentToDate TEXT, InfoReceivedPSDate TEXT,
        latitude REAL, longitude REAL, BriefFacts TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ActSectionAssociation (
        CaseMasterID INTEGER NOT NULL,
        ActID INTEGER, SectionID INTEGER, ActOrderID INTEGER, SectionOrderID INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS ChargesheetDetails (
        CSID INTEGER PRIMARY KEY,
        CaseMasterID INTEGER NOT NULL,
        csdate TEXT, cstype TEXT, PolicePersonID INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS Accused (
        AccusedMasterID INTEGER PRIMARY KEY,
        CaseMasterID INTEGER NOT NULL,
        AccusedName TEXT, AgeYear INTEGER, GenderID TEXT, PersonID TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS Victim (
        VictimMasterID INTEGER PRIMARY KEY,
        CaseMasterID INTEGER NOT NULL,
        VictimName TEXT, AgeYear INTEGER, GenderID TEXT, VictimPolice TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ComplainantDetails (
        ComplainantID INTEGER PRIMARY KEY,
        CaseMasterID INTEGER NOT NULL,
        ComplainantName TEXT, AgeYear INTEGER,
        OccupationID INTEGER, ReligionID INTEGER, CasteID INTEGER, GenderID TEXT
    )""",
]


def connect(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    for ddl in _DDL:
        conn.execute(ddl)
    return conn
