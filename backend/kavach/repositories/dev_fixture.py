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
    # -- legal & classification lookups (ER-004/#9) ----------------------
    """CREATE TABLE IF NOT EXISTS Act (
        ActCode TEXT PRIMARY KEY, ActDescription TEXT, ShortName TEXT, Active INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS Section (
        ActCode TEXT NOT NULL, SectionCode TEXT NOT NULL,
        SectionDescription TEXT, Active INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS CrimeHeadActSection (
        CrimeHeadID INTEGER NOT NULL, ActCode TEXT NOT NULL, SectionCode TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS CrimeHead (
        CrimeHeadID INTEGER PRIMARY KEY, CrimeGroupName TEXT, Active INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS CrimeSubHead (
        CrimeSubHeadID INTEGER PRIMARY KEY, CrimeHeadID INTEGER,
        CrimeHeadName TEXT, SeqID INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS CaseCategory (
        CaseCategoryID INTEGER PRIMARY KEY, LookupValue TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS GravityOffence (
        GravityOffenceID INTEGER PRIMARY KEY, LookupValue TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS CaseStatusMaster (
        CaseStatusID INTEGER PRIMARY KEY, CaseStatusName TEXT
    )""",
    # -- geography / org hierarchy / demographic masters (ER-005/#10) -----
    """CREATE TABLE IF NOT EXISTS State (
        StateID INTEGER PRIMARY KEY, StateName TEXT, NationalityID INTEGER, Active INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS District (
        DistrictID INTEGER PRIMARY KEY, DistrictName TEXT, StateID INTEGER, Active INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS Court (
        CourtID INTEGER PRIMARY KEY, CourtName TEXT,
        DistrictID INTEGER, StateID INTEGER, Active INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS UnitType (
        UnitTypeID INTEGER PRIMARY KEY, UnitTypeName TEXT,
        CityDistState TEXT, Hierarchy INTEGER, Active INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS Unit (
        UnitID INTEGER PRIMARY KEY, UnitName TEXT, TypeID INTEGER, ParentUnit INTEGER,
        NationalityID INTEGER, StateID INTEGER, DistrictID INTEGER, Active INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS Rank (
        RankID INTEGER PRIMARY KEY, RankName TEXT, Hierarchy INTEGER, Active INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS Designation (
        DesignationID INTEGER PRIMARY KEY, DesignationName TEXT,
        Active INTEGER, SortOrder INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS Employee (
        EmployeeID INTEGER PRIMARY KEY, DistrictID INTEGER, UnitID INTEGER,
        RankID INTEGER, DesignationID INTEGER, KGID TEXT, FirstName TEXT,
        EmployeeDOB TEXT, GenderID TEXT, BloodGroupID INTEGER,
        PhysicallyChallenged INTEGER, AppointmentDate TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS CasteMaster (
        caste_master_id INTEGER PRIMARY KEY, caste_master_name TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ReligionMaster (
        ReligionID INTEGER PRIMARY KEY, ReligionName TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS OccupationMaster (
        OccupationID INTEGER PRIMARY KEY, OccupationName TEXT
    )""",
    # -- arrest/surrender events (ER-006/#11) -----------------------------
    """CREATE TABLE IF NOT EXISTS ArrestSurrender (
        ArrestSurrenderID INTEGER PRIMARY KEY, CaseMasterID INTEGER NOT NULL,
        ArrestSurrenderTypeID INTEGER, ArrestSurrenderDate TEXT,
        ArrestSurrenderStateId INTEGER, ArrestSurrenderDistrictId INTEGER,
        PoliceStationID INTEGER, IOID INTEGER, CourtID INTEGER,
        AccusedMasterID INTEGER, IsAccused INTEGER, IsComplainantAccused INTEGER
    )""",
]


def connect(path: str = ":memory:", *, check_same_thread: bool = True) -> sqlite3.Connection:
    """check_same_thread=False is for read-only multi-thread serving (the API
    graph store); writers must stay single-threaded."""
    conn = sqlite3.connect(path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    for ddl in _DDL:
        conn.execute(ddl)
    return conn
