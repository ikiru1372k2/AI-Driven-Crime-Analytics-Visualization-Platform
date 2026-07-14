"""Lookup/reference table rows for the SYNTHETIC dataset (DATA-001/#14).

Row dicts use EXACT documented physical column names (schema-manifest.json).
All names/labels are synthetic; demographic master values are deliberately
generic placeholders (this is demo data, ADR-011).
"""

from random import Random

from kavach.datagen import config as cfg


def build_lookups(rng: Random) -> tuple[dict[str, list[dict]], dict]:
    """Returns (tables, context). Context carries helper indexes used by the
    case generator (stations, employees per unit, courts per district)."""
    t: dict[str, list[dict]] = {}
    state_id, state_name = cfg.STATE

    t["State"] = [{"StateID": state_id, "StateName": state_name,
                   "NationalityID": 1, "Active": 1}]
    t["District"] = [
        {"DistrictID": d, "DistrictName": name, "StateID": state_id, "Active": 1}
        for d, name, _ in cfg.DISTRICTS
    ]
    t["UnitType"] = [
        {"UnitTypeID": 1, "UnitTypeName": "Police Station", "CityDistState": "City",
         "Hierarchy": 5, "Active": 1},
        {"UnitTypeID": 2, "UnitTypeName": "District Office", "CityDistState": "District",
         "Hierarchy": 3, "Active": 1},
    ]

    units, employees, courts = [], [], []
    stations = []  # (unit_id, district_id, lat, lon)
    emp_by_unit: dict[int, list[int]] = {}
    court_by_district: dict[int, int] = {}
    emp_id = 9000
    for d_id, d_name, sts in cfg.DISTRICTS:
        hq_id = d_id  # district office unit id == district id (synthetic convention)
        units.append({"UnitID": hq_id, "UnitName": f"{d_name} District Police Office",
                      "TypeID": 2, "ParentUnit": None, "NationalityID": 1,
                      "StateID": state_id, "DistrictID": d_id, "Active": 1})
        court_id = 100 + d_id
        courts.append({"CourtID": court_id, "CourtName": f"{d_name} District Court",
                       "DistrictID": d_id, "StateID": state_id, "Active": 1})
        court_by_district[d_id] = court_id
        for u_id, u_name, lat, lon in sts:
            units.append({"UnitID": u_id, "UnitName": u_name, "TypeID": 1,
                          "ParentUnit": hq_id, "NationalityID": 1,
                          "StateID": state_id, "DistrictID": d_id, "Active": 1})
            stations.append((u_id, d_id, lat, lon))
            emp_by_unit[u_id] = []
            for rank_id, desig_id in ((5, 2), (4, 1)):  # registrar SHO + IO
                emp_id += 1
                first = rng.choice(cfg.FIRST_NAMES_M + cfg.FIRST_NAMES_F)
                employees.append({
                    "EmployeeID": emp_id, "DistrictID": d_id, "UnitID": u_id,
                    "RankID": rank_id, "DesignationID": desig_id,
                    "KGID": f"KG{emp_id}", "FirstName": first,
                    "EmployeeDOB": f"19{rng.randint(70, 95)}-0{rng.randint(1, 9)}-15",
                    "GenderID": rng.choice(["M", "F"]), "BloodGroupID": rng.randint(1, 8),
                    "PhysicallyChallenged": 0,
                    "AppointmentDate": f"20{rng.randint(5, 20):02d}-06-01",
                })
                emp_by_unit[u_id].append(emp_id)
    t["Unit"], t["Employee"], t["Court"] = units, employees, courts

    t["Rank"] = [
        {"RankID": 4, "RankName": "Police Sub-Inspector", "Hierarchy": 4, "Active": 1},
        {"RankID": 5, "RankName": "Police Inspector", "Hierarchy": 3, "Active": 1},
    ]
    t["Designation"] = [
        {"DesignationID": 1, "DesignationName": "Investigating Officer", "Active": 1,
         "SortOrder": 2},
        {"DesignationID": 2, "DesignationName": "SHO", "Active": 1, "SortOrder": 1},
    ]

    t["CrimeHead"] = [{"CrimeHeadID": h, "CrimeGroupName": n, "Active": 1}
                      for h, n in cfg.CRIME_HEADS]
    t["CrimeSubHead"] = [
        {"CrimeSubHeadID": s, "CrimeHeadID": h, "CrimeHeadName": n, "SeqID": i + 1}
        for i, (s, h, n) in enumerate(cfg.CRIME_SUBHEADS)
    ]
    t["Act"] = [{"ActCode": "1", "ActDescription": "Indian Penal Code",
                 "ShortName": "IPC", "Active": 1}]
    sections = sorted({sec for secs in cfg.SUBHEAD_SECTIONS.values() for sec in secs})
    t["Section"] = [{"ActCode": "1", "SectionCode": s,
                     "SectionDescription": f"IPC Section {s}", "Active": 1}
                    for s in sections]
    t["CrimeHeadActSection"] = [
        {"CrimeHeadID": h, "ActCode": "1", "SectionCode": sec}
        for s, h, _ in cfg.CRIME_SUBHEADS for sec in cfg.SUBHEAD_SECTIONS[s]
    ]
    t["CaseCategory"] = [{"CaseCategoryID": i, "LookupValue": v}
                         for i, v in cfg.CASE_CATEGORIES]
    t["GravityOffence"] = [{"GravityOffenceID": i, "LookupValue": v} for i, v in cfg.GRAVITY]
    t["CaseStatusMaster"] = [{"CaseStatusID": i, "CaseStatusName": v}
                             for i, v in cfg.CASE_STATUSES]

    # Demographic masters — generic synthetic placeholders (ADR-009/ADR-011)
    t["ReligionMaster"] = [{"ReligionID": i, "ReligionName": f"Religion {c}"}
                           for i, c in enumerate("ABCD", 1)]
    t["CasteMaster"] = [{"caste_master_id": i, "caste_master_name": f"Community {c}"}
                        for i, c in enumerate("ABCDEF", 1)]
    t["OccupationMaster"] = [
        {"OccupationID": i, "OccupationName": n}
        for i, n in enumerate(["Farmer", "Government Employee", "Private Employee",
                               "Business", "Student", "Driver", "Homemaker", "Retired"], 1)
    ]

    ctx = {
        "stations": stations,
        "emp_by_unit": emp_by_unit,
        "court_by_district": court_by_district,
        "district_of_unit": {u: d for u, d, _, _ in stations},
        "station_coords": {u: (lat, lon) for u, _, lat, lon in stations},
    }
    return t, ctx
