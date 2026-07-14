# Field Mapping — Legal & Classification Lookups (ER-004 / #9)

Physical names exact per docs/schema/er-conformance-matrix.md §1.7–1.11, §1.15, §1.24, §1.25.

| Database | Domain / API | Notes |
|---|---|---|
| Act.ActCode | act_code | PK (VARCHAR) |
| Act.ActDescription / ShortName / Active | act_description / short_name / active | BIT→bool adaptation (type only, documented) |
| Section.ActCode + SectionCode | act_code + section_code | Q4: no documented PK — composite identity |
| Section.SectionDescription / Active | section_description / active | |
| CrimeHeadActSection.CrimeHeadID/ActCode/SectionCode | crime_head_id/act_code/section_code | junction, no PK (Q4) |
| CrimeHead.CrimeHeadID / CrimeGroupName / Active | crime_head_id / crime_group_name / active | |
| CrimeSubHead.CrimeHeadName | **crime_sub_head_name** | **Q5: source column holds the sub-head name** |
| CrimeSubHead.CrimeSubHeadID / CrimeHeadID / SeqID | crime_sub_head_id / crime_head_id / seq_id | |
| CaseCategory.CaseCategoryID / LookupValue | case_category_id / lookup_value | FIR/UDR/PAR… |
| GravityOffence.GravityOffenceID / LookupValue | gravity_offence_id / lookup_value | Heinous/Non-Heinous |
| CaseStatusMaster.CaseStatusID / CaseStatusName | case_status_id / case_status_name | |

**Q3 join rule:** `ActSectionAssociation.ActID/SectionID` (INT in source) resolve to `Act.ActCode`/`Section.SectionCode` (VARCHAR) by string value: `resolve_act(act_id)` / `resolve_section(act_id, section_id)` in `classification_repository.ClassificationResolver`. Dangling references resolve to `None` — surfaced, never invented.

**Consistency signal:** `subhead_consistent(case)` flags (never fixes) a CrimeMinorHeadID whose parent CrimeHeadID differs from the case's CrimeMajorHeadID — reported through data-quality metrics (DATA-002).
