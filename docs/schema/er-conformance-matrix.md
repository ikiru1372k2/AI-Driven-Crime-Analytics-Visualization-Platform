# FIR ER Schema Conformance Matrix

**Status:** AUTHORITATIVE — Source of truth is the supplied *Police FIR System — ER Diagram* (Karnataka Police Department, Database Design Document).
**Rule:** No source column may be invented, renamed in persistence, or semantically redefined. All derived/AI tables are catalogued separately in [derived-intelligence-schema.md](derived-intelligence-schema.md).

Legend — **Sensitivity:** `HIGH` (person PII / protected demographics), `MED` (person-adjacent), `LOW` (reference/lookup).
**Class:** every field consumed by analytics is classified `OBSERVED`, `DERIVED`, `AI_DERIVED`, `EXTERNAL`, or `HUMAN_CONFIRMED`. All columns in this file are `OBSERVED` source fields.

---

## 1. Table Catalogue

### 1.1 CaseMaster — core FIR/case record
| Column | Type | Key | Notes |
|---|---|---|---|
| CaseMasterID | INT | PK | Authoritative FIR/case identifier |
| CrimeNo | VARCHAR | | Structured: 1-digit category code + 4-digit district + 4-digit station (UnitID) + 4-digit year + 5-digit serial. Serial is per station × category × year |
| CaseNo | VARCHAR | | YYYY + 5-digit serial = last 9 digits of CrimeNo |
| CrimeRegisteredDate | DATE | | Registration date — NOT occurrence date |
| PolicePersonID | INT | FK → Employee.EmployeeID | Registering officer |
| PoliceStationID | INT | FK → Unit.UnitID | Registering station |
| CaseCategoryID | INT | FK → CaseCategory.CaseCategoryID | FIR / UDR / PAR / Zero FIR |
| GravityOffenceID | INT | FK → GravityOffence.GravityOffenceID | Heinous / Non-Heinous |
| CrimeMajorHeadID | INT | FK → CrimeHead.CrimeHeadID | Major head |
| CrimeMinorHeadID | INT | FK → CrimeSubHead.CrimeSubHeadID | Minor head |
| CaseStatusID | INT | FK → CaseStatusMaster.CaseStatusID | Current status |
| CourtID | INT | FK → Court.CourtID | Trial court |
| IncidentFromDate | DATETIME | | Occurrence start — authoritative for temporal analytics |
| IncidentToDate | DATETIME | | Occurrence end |
| InfoReceivedPSDate | DATETIME | | When station received information |
| latitude | DECIMAL | | Incident GPS latitude |
| longitude | DECIMAL | | Incident GPS longitude |
| BriefFacts | NVARCHAR(MAX) | | Unstructured narrative — sole input to MO extraction |

Sensitivity: MED (BriefFacts may contain names → treat HIGH in exposure paths).

### 1.2 ComplainantDetails — complainants of a case
| Column | Type | Key | Notes |
|---|---|---|---|
| ComplainantID | INT | PK | |
| CaseMasterID | INT | FK → CaseMaster | 1 case : N complainants |
| ComplainantName | VARCHAR | | PII |
| AgeYear | INT | | |
| OccupationID | INT | FK → OccupationMaster | **Complainant** occupation |
| ReligionID | INT | FK → ReligionMaster | **Complainant** religion — protected |
| CasteID | INT | FK → CasteMaster.caste_master_id | **Complainant** caste — protected |
| GenderID | INT | lookup | |

Sensitivity: HIGH. **PROHIBITED:** using ReligionID/CasteID/OccupationID as offender/area profiling features. These are complainant attributes only (see ADR-009).

### 1.3 ActSectionAssociation — acts/sections invoked per case (junction, no documented PK)
| Column | Type | Key | Notes |
|---|---|---|---|
| CaseMasterID | INT | FK → CaseMaster | |
| ActID | INT | FK → Act.ActCode | Doc types ActID as INT but Act.ActCode as VARCHAR — **documented type inconsistency**, preserve as-is and join on value |
| SectionID | INT | FK → Section.SectionCode | Same inconsistency (SectionCode is VARCHAR) |
| ActOrderID | INT | | Print order of act |
| SectionOrderID | INT | | Print order of section |

Implied composite identity: (CaseMasterID, ActID, SectionID).

### 1.4 Victim
| Column | Type | Key | Notes |
|---|---|---|---|
| VictimMasterID | INT | PK | |
| CaseMasterID | INT | FK → CaseMaster | 1 case : N victims |
| VictimName | VARCHAR | | PII — never exposed in state-level analytics |
| AgeYear | INT | | |
| GenderID | INT | lookup | values like m/f/t |
| VictimPolice | VARCHAR | | "1" if victim is police else "0" — **string flag, not BIT** (documented as-is) |

Sensitivity: HIGH.

### 1.5 Accused
| Column | Type | Key | Notes |
|---|---|---|---|
| AccusedMasterID | INT | PK | Per-case accused record — **NOT a person identity** |
| CaseMasterID | INT | FK → CaseMaster | 1 case : N accused |
| AccusedName | VARCHAR | | PII |
| AgeYear | INT | | |
| GenderID | INT | lookup | M/F/T |
| PersonID | VARCHAR | | **Accused ordering within a case: A1, A2, A3…** |

Sensitivity: HIGH.
**SEMANTIC GUARD (ADR-003):** `PersonID` is a per-case sort label. It MUST NOT be used as a state-wide person key, for repeat-offender identity, or as a graph identity key. Cross-FIR identity exists only as the derived `EntityResolutionCandidate` (AI_DERIVED) and `ResolvedIdentity` (HUMAN_CONFIRMED) entities.

### 1.6 ArrestSurrender
| Column | Type | Key | Notes |
|---|---|---|---|
| ArrestSurrenderID | INT | PK | |
| CaseMasterID | INT | FK → CaseMaster | |
| ArrestSurrenderTypeID | INT | lookup | arrest vs voluntary surrender |
| ArrestSurrenderDate | DATE | | |
| ArrestSurrenderStateId | INT | FK → State.StateID | |
| ArrestSurrenderDistrictId | INT | FK → District.DistrictID | |
| PoliceStationID | INT | FK → Unit.UnitID | |
| IOID | INT | FK → Employee.EmployeeID | Investigating Officer |
| CourtID | INT | FK → Court.CourtID | |
| AccusedMasterID | INT | FK → Accused.AccusedMasterID | |
| IsAccused | BIT | | primary accused flag |
| IsComplainantAccused | BIT | | complainant also accused |

### 1.7 Act
| Column | Type | Key |
|---|---|---|
| ActCode | VARCHAR | PK |
| ActDescription | VARCHAR | |
| ShortName | VARCHAR | |
| Active | BIT | |

### 1.8 Section — no documented PK; implied composite (ActCode, SectionCode)
| Column | Type | Key |
|---|---|---|
| ActCode | VARCHAR | FK → Act.ActCode |
| SectionCode | VARCHAR | |
| SectionDescription | VARCHAR | |
| Active | BIT | |

### 1.9 CrimeHeadActSection — junction (no documented PK)
| Column | Type | Key |
|---|---|---|
| CrimeHeadID | INT | FK → CrimeHead |
| ActCode | VARCHAR | FK → Act |
| SectionCode | VARCHAR | |

### 1.10 CrimeHead
| Column | Type | Key |
|---|---|---|
| CrimeHeadID | INT | PK |
| CrimeGroupName | VARCHAR | |
| Active | BIT | |

### 1.11 CrimeSubHead
| Column | Type | Key |
|---|---|---|
| CrimeSubHeadID | INT | PK |
| CrimeHeadID | INT | FK → CrimeHead |
| CrimeHeadName | VARCHAR | (name of the **sub-head**, per doc) |
| SeqID | INT | |

### 1.12 CasteMaster — note snake_case source naming (documented as-is)
| Column | Type | Key |
|---|---|---|
| caste_master_id | INT | PK |
| caste_master_name | VARCHAR | |

Sensitivity: HIGH (protected attribute lookup).

### 1.13 ReligionMaster
| Column | Type | Key |
|---|---|---|
| ReligionID | INT | PK |
| ReligionName | VARCHAR | |

Sensitivity: HIGH (protected attribute lookup).

### 1.14 OccupationMaster
| Column | Type | Key |
|---|---|---|
| OccupationID | INT | PK |
| OccupationName | VARCHAR | |

### 1.15 CaseStatusMaster
| Column | Type | Key |
|---|---|---|
| CaseStatusID | INT | PK |
| CaseStatusName | VARCHAR | e.g. Under Investigation, Charge Sheeted, Closed |

### 1.16 Court
| Column | Type | Key |
|---|---|---|
| CourtID | INT | PK |
| CourtName | VARCHAR | |
| DistrictID | INT | FK → District |
| StateID | INT | FK → State |
| Active | BIT | |

### 1.17 District
| Column | Type | Key |
|---|---|---|
| DistrictID | INT | PK |
| DistrictName | VARCHAR | |
| StateID | INT | FK → State |
| Active | BIT | |

### 1.18 State
| Column | Type | Key |
|---|---|---|
| StateID | INT | PK |
| StateName | VARCHAR | |
| NationalityID | INT | (no documented FK target) |
| Active | BIT | |

### 1.19 Unit — police unit / station, self-referencing hierarchy
| Column | Type | Key |
|---|---|---|
| UnitID | INT | PK |
| UnitName | VARCHAR | |
| TypeID | INT | FK → UnitType.UnitTypeID |
| ParentUnit | INT | self-reference → Unit.UnitID |
| NationalityID | INT | (no documented FK target) |
| StateID | INT | FK → State |
| DistrictID | INT | FK → District |
| Active | BIT | |

### 1.20 UnitType
| Column | Type | Key |
|---|---|---|
| UnitTypeID | INT | PK |
| UnitTypeName | VARCHAR | |
| CityDistState | VARCHAR | operational level: City/District/State |
| Hierarchy | INT | lower = higher authority |
| Active | BIT | |

### 1.21 Rank
| Column | Type | Key |
|---|---|---|
| RankID | INT | PK |
| RankName | VARCHAR | |
| Hierarchy | INT | lower = higher rank |
| Active | BIT | |

### 1.22 Designation
| Column | Type | Key |
|---|---|---|
| DesignationID | INT | PK |
| DesignationName | VARCHAR | |
| Active | BIT | |
| SortOrder | INT | |

### 1.23 Employee
| Column | Type | Key |
|---|---|---|
| EmployeeID | INT | PK |
| DistrictID | INT | FK → District |
| UnitID | INT | FK → Unit |
| RankID | INT | FK → Rank |
| DesignationID | INT | FK → Designation |
| KGID | VARCHAR | Karnataka Government ID |
| FirstName | VARCHAR | PII |
| EmployeeDOB | DATE | PII |
| GenderID | INT | lookup |
| BloodGroupID | INT | lookup |
| PhysicallyChallenged | BIT | sensitive |
| AppointmentDate | DATE | |

Sensitivity: MED–HIGH (employee PII minimized in analytics views).

### 1.24 CaseCategory
| Column | Type | Key |
|---|---|---|
| CaseCategoryID | INT | PK |
| LookupValue | VARCHAR | FIR, UDR, PAR… |

### 1.25 GravityOffence
| Column | Type | Key |
|---|---|---|
| GravityOffenceID | INT | PK |
| LookupValue | VARCHAR | Heinous / Non-Heinous |

### 1.26 ChargesheetDetails
| Column | Type | Key | Notes |
|---|---|---|---|
| CSID | INT | PK | |
| CaseMasterID | INT | FK → CaseMaster | (source description contains a copy-paste artifact: "filed by this complainant") |
| csdate | DATETIME | | chargesheet date |
| cstype | CHAR | | A=Chargesheet, B=False Case, C=Undetected |
| PolicePersonID | INT | FK → Employee.EmployeeID | source writes "employeeMaster.employee ID" — resolved to Employee |

---

## 2. Referenced-but-Undefined Tables (documented deviation)

The relationship matrix references two tables that have **no table-definition section** in the source document:

| Table | Referenced relationship | Handling |
|---|---|---|
| `Inv_OccuranceTime` | CaseMaster 1:1 Inv_OccuranceTime — "One FIR has one occurrence time/location record" | Column set undocumented. CaseMaster already carries IncidentFromDate/To/lat/long, so occurrence analytics uses CaseMaster only. Do NOT invent columns. Status: `DEVIATION: UNDEFINED_IN_SOURCE` |
| `inv_arrestsurrenderaccused` | Junction: ArrestSurrender 1:N junction; junction N:1 ArrestSurrender (ArrestSurrenderID both sides) | Column set undocumented beyond ArrestSurrenderID. ArrestSurrender.AccusedMasterID already links accused directly; the junction is not required for MVP analytics. Status: `DEVIATION: UNDEFINED_IN_SOURCE` |

## 3. Relationship Matrix (as documented)

| Parent | Parent Col | Cardinality | Child | Child Col |
|---|---|---|---|---|
| CaseMaster | CaseMasterID | 1:N | Victim | CaseMasterID |
| CaseMaster | CaseMasterID | 1:N | Accused | CaseMasterID |
| CaseMaster | CaseMasterID | 1:N | ArrestSurrender | CaseMasterID |
| CaseMaster | CaseMasterID | 1:N | ComplainantDetails | CaseMasterID |
| CaseMaster | CaseMasterID | 1:N | ActSectionAssociation | CaseMasterID |
| CaseMaster | CaseMasterID | 1:1 | Inv_OccuranceTime | CaseMasterID |
| CaseCategory | CaseCategoryID | 1:N | CaseMaster | CaseCategoryID |
| GravityOffence | GravityOffenceID | 1:N | CaseMaster | GravityOffenceID |
| CrimeHead | CrimeHeadID | 1:N | CaseMaster | CrimeMajorHeadID |
| CrimeSubHead | CrimeSubHeadID | 1:N | CaseMaster | CrimeMinorHeadID |
| CaseStatusMaster | CaseStatusID | 1:N | CaseMaster | CaseStatusID |
| Court | CourtID | 1:N | CaseMaster | CourtID |
| Employee | EmployeeID | 1:N | CaseMaster | PolicePersonID |
| ArrestSurrender | ArrestSurrenderID | 1:N | inv_arrestsurrenderaccused | ArrestSurrenderID |
| State | StateID | 1:N | ArrestSurrender | ArrestSurrenderStateId |
| District | DistrictID | 1:N | ArrestSurrender | ArrestSurrenderDistrictId |
| Court | CourtID | 1:N | ArrestSurrender | CourtID |
| Employee | EmployeeID | 1:N | ArrestSurrender | IOID |
| OccupationMaster | OccupationID | 1:N | ComplainantDetails | OccupationID |
| ReligionMaster | ReligionID | 1:N | ComplainantDetails | ReligionID |
| CasteMaster | caste_master_id | 1:N | ComplainantDetails | CasteID |
| Act | ActCode | 1:N | ActSectionAssociation | ActID |
| Section | SectionCode | 1:N | ActSectionAssociation | SectionID |
| CrimeHead | CrimeHeadID | 1:N | CrimeSubHead | CrimeHeadID |
| CrimeHead | CrimeHeadID | 1:N | CrimeHeadActSection | CrimeHeadID |
| Act | ActCode | 1:N | CrimeHeadActSection | ActCode |
| Act | ActCode | 1:N | Section | ActCode |
| District | DistrictID | 1:N | Court | DistrictID |
| State | StateID | 1:N | District | StateID |
| UnitType | UnitTypeID | 1:N | Unit | TypeID |
| State | StateID | 1:N | Unit | StateID |
| District | DistrictID | 1:N | Unit | DistrictID |
| District | DistrictID | 1:N | Employee | DistrictID |
| Unit | UnitID | 1:N | Employee | UnitID |
| Rank | RankID | 1:N | Employee | RankID |
| Designation | DesignationID | 1:N | Employee | DesignationID |

## 4. Documented Source Quirks (preserve, do not "fix" silently)

| # | Quirk | Handling |
|---|---|---|
| Q1 | `Accused.PersonID` is per-case ordering (A1, A2…) | Semantic guard; never a person key (ADR-003) |
| Q2 | `Victim.VictimPolice` is VARCHAR "1"/"0", not BIT | Parse defensively; keep source type |
| Q3 | `ActSectionAssociation.ActID/SectionID` typed INT while targets are VARCHAR codes | Join on value; document per-dataset resolution during ingestion |
| Q4 | `Section` and `ActSectionAssociation` and `CrimeHeadActSection` have no documented PK | Use implied composite keys; enforce uniqueness in ingestion validation only |
| Q5 | `CrimeSubHead.CrimeHeadName` holds the *sub-head* name | Map to domain `crimeSubHeadName`, mapping documented |
| Q6 | `CasteMaster` uses snake_case columns | Preserve physical names |
| Q7 | `ChargesheetDetails.CaseMasterID` description copy-paste artifact | FK semantics = case linkage |
| Q8 | `Inv_OccuranceTime`, `inv_arrestsurrenderaccused` undefined | See §2 |
| Q9 | `NationalityID` (State, Unit) has no documented target table | Store as plain INT; no invented FK |
| Q10 | Complainant demographics are complainant-only | Never offender/area profiling features (ADR-009) |

## 5. Data Store / Domain / API Mapping Convention

Physical Catalyst Data Store tables preserve **exact documented column names**. Application-layer mapping (documented per entity in `backend/` models):

```
DATABASE (as documented)   DOMAIN (python)        API (json)
CaseMaster.CaseMasterID  → case_master_id       → case_master_id
CaseMaster.IncidentFromDate → incident_from_date → incident_from_date
CaseMaster.latitude      → latitude             → latitude
CasteMaster.caste_master_id → caste_master_id   → caste_master_id
```

Analytics feature lineage example (documented per engine spec):

```
CaseMaster.IncidentFromDate → incident_from_date → incident_hour → cyclic_hour_sin / cyclic_hour_cos
```

## 6. Conformance Gate Checklist

- [x] Every source ER table catalogued (26 defined + 2 referenced-undefined)
- [x] Every documented PK recorded
- [x] Every documented FK recorded
- [x] Every documented cardinality captured (§3)
- [x] CaseMaster / Accused / Victim / Complainant / ArrestSurrender / Act–Section / CrimeHead–SubHead / Unit hierarchy / Employee / ChargesheetDetails semantics validated (§1, §4)
- [x] No invented source columns
- [x] No silently changed field meaning (quirks table §4)
- [ ] Derived tables marked DERIVED — see derived-intelligence-schema.md (PROV-001)
- [ ] AI-generated attributes marked AI_DERIVED (MO-001, ENT-002)
- [ ] Human-reviewed intelligence marked HUMAN_CONFIRMED (ENT-003)

Gate items left unchecked are completed by the referenced backlog issues; analytics issues depending on the FIR model cannot close until their mappings pass this gate.
