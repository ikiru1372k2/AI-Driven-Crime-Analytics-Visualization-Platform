# Field Mapping — Case Core (ER-002 / #7)

Convention: `DATABASE (documented ER name) → DOMAIN (python) → API (json)`.
Physical names are exact per docs/schema/er-conformance-matrix.md; API layer
uses the domain snake_case names verbatim.

## CaseMaster → kavach.domain.case.CaseMaster
| Database | Domain / API | Notes |
|---|---|---|
| CaseMasterID | case_master_id | PK, authoritative case identifier |
| CrimeNo | crime_no | stored verbatim; structured parsing is DERIVED (future helper) |
| CaseNo | case_no | verbatim |
| CrimeRegisteredDate | crime_registered_date | registration — never occurrence time |
| PolicePersonID | police_person_id | FK Employee |
| PoliceStationID | police_station_id | FK Unit |
| CaseCategoryID | case_category_id | FK CaseCategory |
| GravityOffenceID | gravity_offence_id | FK GravityOffence |
| CrimeMajorHeadID | crime_major_head_id | FK CrimeHead |
| CrimeMinorHeadID | crime_minor_head_id | FK CrimeSubHead |
| CaseStatusID | case_status_id | FK CaseStatusMaster |
| CourtID | court_id | FK Court |
| IncidentFromDate | incident_from_date | **occurrence-time source** (`occurrence_time()`) |
| IncidentToDate | incident_to_date | |
| InfoReceivedPSDate | info_received_ps_date | |
| latitude | latitude | lowercase in source — preserved |
| longitude | longitude | lowercase in source — preserved |
| BriefFacts | brief_facts | MO extraction input (MO-001/#38) |

Analytics lineage (HOT-001/#28): `IncidentFromDate → incident_from_date → incident_hour → cyclic_hour_sin / cyclic_hour_cos`.

## ActSectionAssociation → kavach.domain.case.ActSectionAssociation
| Database | Domain / API | Notes |
|---|---|---|
| CaseMasterID | case_master_id | FK CaseMaster |
| ActID | act_id | Q3: INT in source, joined by value to Act.ActCode (VARCHAR) |
| SectionID | section_id | Q3: joined by value to Section.SectionCode |
| ActOrderID | act_order_id | print order |
| SectionOrderID | section_order_id | print order |

No documented PK (Q4); implied composite (CaseMasterID, ActID, SectionID).

## ChargesheetDetails → kavach.domain.case.ChargesheetDetails
| Database | Domain / API | Notes |
|---|---|---|
| CSID | csid | PK |
| CaseMasterID | case_master_id | FK CaseMaster (Q7 description artifact noted) |
| csdate | csdate | lowercase in source — preserved |
| cstype | cstype | A/B/C documented; other values preserved + flagged via `cstype_known` |
| PolicePersonID | police_person_id | FK Employee (source writes "employeeMaster") |
