# Field Mapping — Geography, Org Hierarchy & Demographic Masters (ER-005 / #10)

Physical names exact per docs/schema/er-conformance-matrix.md §1.12–1.14, §1.16–1.23.

| Database | Domain / API | Notes |
|---|---|---|
| State.StateID / StateName / NationalityID / Active | state_id / state_name / nationality_id / active | Q9: NationalityID plain INT, no invented FK |
| District.DistrictID / DistrictName / StateID / Active | district_id / district_name / state_id / active | |
| Court.CourtID / CourtName / DistrictID / StateID / Active | court_id / court_name / district_id / state_id / active | |
| UnitType.UnitTypeID / UnitTypeName / CityDistState / Hierarchy / Active | unit_type_id / unit_type_name / city_dist_state / hierarchy / active | lower Hierarchy = higher authority |
| Unit.UnitID / UnitName / TypeID / ParentUnit / NationalityID / StateID / DistrictID / Active | unit_id / unit_name / type_id / parent_unit / nationality_id / state_id / district_id / active | ParentUnit self-reference (cycle-protected resolver) |
| Rank.RankID / RankName / Hierarchy / Active | rank_id / rank_name / hierarchy / active | |
| Designation.DesignationID / DesignationName / Active / SortOrder | designation_id / designation_name / active / sort_order | |
| Employee.* (12 cols) | employee_id … appointment_date | KGID / FirstName / EmployeeDOB / BloodGroupID / PhysicallyChallenged = sensitive; `EmployeeAnalyticsView` exposes only employee_id + org FKs |
| CasteMaster.caste_master_id / caste_master_name | caste_master_id / caste_master_name | **Q6: snake_case physical names preserved** |
| ReligionMaster.ReligionID / ReligionName | religion_id / religion_name | ADR-009: complainant-context only |
| OccupationMaster.OccupationID / OccupationName | occupation_id / occupation_name | ADR-009: complainant-context only |

**Hierarchy resolution (`UnitHierarchyResolver`):** unit → district/state from its own FKs, falling back up the `ParentUnit` chain when null; memoized O(1) amortized; `HierarchyReport` records cycles and dangling parents as data-quality findings (flagged, never fixed). This resolver is the basis for authorization scoping (SEC-001/#71) and map drill-down (UI-002/#58).
