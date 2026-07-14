=== ISSUE ===
key: EPIC-ANOM
title: [EPIC] Behavioral Anomaly Detection
labels: type:epic, area:anomaly, area:ml, priority:p1
milestone: M7
estimate: -
risk: MEDIUM
blocked_by:
--- BODY ---
## Problem
Incidents deviating from comparable historical patterns go unnoticed in manual review. The challenge demands anomaly call-outs — but an unexplained "94% anomaly" is prohibited; every flag must itemize why.

## Why it matters
C2-R10; demo step D6; anomaly frequency feeds area risk.

## Technical scope
Cohort-based feature engineering, IsolationForest/LOF + robust per-feature deviations, mandatory factor explanations, validation suite.

## Out of scope
UI ({{UI-008}}); individual-person risk (prohibited, ADR-005).

## Source data
CaseMaster (time/place/category), Victim aggregates (age band, count), Accused count, MoProfile attributes (AI_DERIVED — flagged as such in explanations).

## Catalyst services
Data Store, AppSail.

## Deliverables & success criteria
Ground-truth anomalous case flagged with correct dominant factors; normal cases not flagged; explanation on every flag.

## Risks
Sparse cohorts → minimum cohort size with INSUFFICIENT_COHORT state.

## Demo impact
D6 anomaly call-out.

## Child issues
{{ANOM-001}}, {{ANOM-002}}, {{ANOM-003}}

=== ISSUE ===
key: ANOM-001
title: [FEATURE] Behavioral feature engineering + comparison cohort definition
labels: type:feature, area:anomaly, area:analytics, priority:p1
milestone: M7
estimate: M
risk: MEDIUM
blocked_by: DATA-002, MO-003
--- BODY ---
## Summary
Build per-case behavioral feature vectors and define comparison cohorts (same crime category × district × trailing window): cyclic incident time, location context (distance to category centroid), victim age band/count, accused count, MO attributes (one-hot with UNKNOWN category), with prohibited-feature enforcement.

## Source Data / ER Schema Mapping
OBSERVED: CaseMaster (IncidentFromDate, lat/long, CrimeMajorHeadID, PoliceStationID), Victim (AgeYear, count — no names), Accused (count only). AI_DERIVED: MoProfile attributes (flagged in feature manifest). PROHIBITED: ComplainantDetails.ReligionID/CasteID/OccupationID (ADR-009 manifest test).

## ER Conformance Requirements
Feature manifest file lists every input column with classification; CI test asserts prohibited columns absent.

## Dependencies
Blocked by: {{DATA-002}}, {{MO-003}} · Blocks: {{ANOM-002}}

## Edge Cases
Cohort < 30 cases → INSUFFICIENT_COHORT (no scoring); cases missing MO profile (MISSING one-hot, not imputed); multi-victim distributions.

## Acceptance Criteria
- [ ] Feature manifest committed; prohibition test green
- [ ] Deterministic vectors; UNKNOWN/MISSING handled without imputation of fake values
- [ ] Cohort assignment unit-tested incl. minimum-size guard

## Definition of Done
Standard DoD + lineage doc.

## Limitations / Non-Goals
Scoring (ANOM-002).

## References
ADR-009; {{HOT-001}} (shared temporal encodings).

=== ISSUE ===
key: ANOM-002
title: [FEATURE] Anomaly scoring (IsolationForest + LOF) with mandatory per-factor explanation
labels: type:feature, area:anomaly, area:ml, priority:p1, risk:model
milestone: M7
estimate: M
risk: MEDIUM
blocked_by: ANOM-001, PROV-001
--- BODY ---
## Summary
Score cases within cohorts using IsolationForest (primary) cross-checked with LOF; flag top deviants only when both agree beyond thresholds; produce mandatory explanations from robust per-feature deviations (|x−median|/MAD per feature → HIGH/MEDIUM/LOW deviation labels).

## Algorithm / Analytical Method
IsolationForest (contamination=auto, seeded) + LOF (k=20) per cohort; flag if IF score ≥ p99 of cohort AND LOF > threshold (versioned `anom v1`); explanation = top-k features by robust deviation with direction ("incident time 03:40 vs cohort median 21:10", "accused count 6 vs median 2"); AI_DERIVED features flagged in explanation text. Score semantics documented (percentile within cohort — NOT a probability). Failure: INSUFFICIENT_COHORT.

## Source Data / ER Schema Mapping
Feature vectors (ANOM-001). Output AnomalyResult (STATISTICAL_INFERENCE) via PROV SDK with evidence = the case + cohort definition.

## Dependencies
Blocked by: {{ANOM-001}}, {{PROV-001}} · Blocks: {{ANOM-003}}, {{RISK-001}}, {{UI-008}}

## Edge Cases
All-similar cohort (no flags — valid); duplicate near-identical cases; feature all-MISSING case (excluded + counted).

## Acceptance Criteria
- [ ] Ground-truth anomalous case flagged with its designed deviant factors ranked top
- [ ] Normal cohort members not flagged (false-positive ceiling documented from synthetic run)
- [ ] Every flag persists factor breakdown; no bare scores (contract test)
- [ ] Deterministic (seeded)

## Test Plan
Unit: deviation math. Validation: ground truth + FP rate ({{ANOM-003}}).

## Definition of Done
Standard DoD.

## Demo Evidence
D6 card: "Why flagged: time pattern HIGH, accused count HIGH, MO deviation MEDIUM."

## Limitations / Non-Goals
Anomaly ≠ crime severity; wording shipped in limitations.

## References
ADR-008; {{PROV-001}}.

=== ISSUE ===
key: ANOM-003
title: [TEST] Anomaly validation suite (known outlier, normal members, sparse cohorts, explanations)
labels: type:test, area:anomaly, area:ml, priority:p1
milestone: M7
estimate: S
risk: LOW
blocked_by: ANOM-002, DATA-001
--- BODY ---
## Summary
Validation: ground-truth outlier flagged with expected factors; normal members unflagged (FP rate report); sparse cohort → INSUFFICIENT_COHORT; explanation completeness contract.

## Acceptance Criteria
- [ ] Ground-truth anomaly detected; dominant factor matches design
- [ ] FP rate on normal synthetic cases ≤ documented ceiling
- [ ] Sparse-cohort fixture refuses scoring
- [ ] Every flagged result has ≥1 factor with direction + magnitude
- [ ] Suite in CI; results into docs/analytics/validation.md

## Dependencies
Blocked by: {{ANOM-002}}, {{DATA-001}} · Blocks: DoD of {{ANOM-002}}

## Definition of Done
Green in CI.

## References
DATA-001 ground truth.

=== ISSUE ===
key: EPIC-RISK
title: [EPIC] Area Risk Intelligence
labels: type:epic, area:risk, area:ml, priority:p0
milestone: M7
estimate: -
risk: HIGH
blocked_by:
--- BODY ---
## Problem
SCRB needs forward-looking, explainable area-level risk (district/station/grid × category) — not individual predictive policing (prohibited, ADR-005) and not hard-coded driver percentages.

## Why it matters
C2-R9 (predictive risk scoring) — demo step D7; the "proactive" half of the product mission.

## Technical scope
Risk feature engineering from prior engines, transparent scoring with real contributions, temporal holdout validation, socio-economic integration boundary.

## Out of scope
Individual scoring (prohibited); causal claims (prohibited, ADR-009).

## Source data
DERIVED: trend deviations, hotspot density/growth, MO recurrence, anomaly frequency; OBSERVED: case velocity per area. EXTERNAL (optional, only if genuine): public area indicators.

## Catalyst services
AppSail, Data Store, Cron; Zia AutoML only if a validated tabular task materializes (documented decision in {{RISK-002}}).

## Deliverables & success criteria
Temporal-holdout-validated scores with real driver contributions; reproducible; limitations shipped.

## Risks
HIGH honesty risk: overclaiming prediction — mitigated by strict validation wording.

## Demo impact
D7 risk panel with drivers.

## Child issues
{{RISK-001}}, {{RISK-002}}, {{RISK-003}}

=== ISSUE ===
key: RISK-001
title: [FEATURE] Area risk feature engineering (velocity, cluster growth, recurrence, anomaly frequency)
labels: type:feature, area:risk, area:analytics, priority:p0
milestone: M7
estimate: M
risk: MEDIUM
blocked_by: HOT-002, TREND-002
--- BODY ---
## Summary
Per (area × category × week) feature table: recent crime velocity (4w count + slope), baseline deviation (TREND-001 z), spatial cluster density + growth (HOT-002 across runs), temporal recurrence (hour-profile concentration), recurring-MO frequency ({{MO-004}} similar-cluster counts, if available), anomaly frequency ({{ANOM-002}}, if available) — with per-feature classification lineage and graceful MISSING degradation.

## Source Data / ER Schema Mapping
OBSERVED: CaseMaster counts per Unit/District. DERIVED inputs from prior engines with run-version pinning (feature row records source run_ids). PROHIBITED: complainant demographics (manifest test). EXTERNAL: socio-economic indicators only behind an explicit integration point defaulting to absent (C2-R8 honesty).

## Dependencies
Blocked by: {{HOT-002}}, {{TREND-002}} · Related: {{MO-004}}, {{ANOM-002}} (optional features) · Blocks: {{RISK-002}}

## Edge Cases
Areas with no hotspot runs (MISSING, not zero — semantics differ); new stations; week alignment across engines.

## Acceptance Criteria
- [ ] Feature table reproducible given pinned source runs
- [ ] Manifest + prohibition test green
- [ ] MISSING vs zero semantics unit-tested
- [ ] Lineage:每 feature → source engine run_id recorded

## Definition of Done
Standard DoD + lineage doc.

## Limitations / Non-Goals
Scoring (RISK-002).

## References
ADR-005; ADR-009.

=== ISSUE ===
key: RISK-002
title: [FEATURE] Transparent area risk scoring with real driver contributions + temporal holdout validation
labels: type:feature, area:risk, area:ml, priority:p0, risk:model
milestone: M7
estimate: L
risk: HIGH
blocked_by: RISK-001, PROV-001
--- BODY ---
## Summary
Score area×category risk 0–100 with a transparent versioned model whose driver percentages are computed, not hard-coded: v1 = documented weighted normalized-feature model; optional v2 = regularized logistic/Poisson model predicting next-week elevated activity, adopted ONLY if it beats v1 baseline on temporal holdout. Every score ships drivers from actual feature contributions, confidence/support level, and limitations.

## Problem Statement
"Peenya 84/100 HIGH with 31% velocity" must be reproducible arithmetic over real features — and validated against future data it hasn't seen (no leakage) — or it's marketing.

## Algorithm / Analytical Method
- v1: score = 100·Σ w_i·norm(f_i) (weights `risk v1` documented; norm = cohort percentile); drivers = w_i·norm(f_i)/Σ (real contributions)
- Target for validation: "elevated next week" = next-week count > baseline+1·MAD (documented)
- Temporal validation: train/calibrate on weeks 1..k, evaluate ranking on week k+1 (rolling); metrics: rank correlation + precision@k for elevated areas; NO future data in any feature (leakage test: features for week t computed only from ≤t−1)
- Zia AutoML decision: attempt only if capability report supports tabular + exportable explanations; adopt only on holdout win; decision documented either way
- Score semantics documented: relative prioritization within Karnataka, not incident probability
- Minimum support: areas with <N cases/26w → LOW_CONFIDENCE tag

## Source Data / ER Schema Mapping
RISK-001 features (DERIVED). Output AreaRiskScore (STATISTICAL_INFERENCE) via PROV SDK: area, category, score, drivers JSON, support, params/model version, validation metrics reference.

## Dependencies
Blocked by: {{RISK-001}}, {{PROV-001}} · Blocks: {{RISK-003}}, {{UI-008}}

## Edge Cases
All-quiet state (scores compress — percentile semantics documented); one dominant area; category sparsity.

## Acceptance Criteria
- [ ] Driver percentages sum to 100% and equal recomputed contributions (test)
- [ ] Leakage test: shifting future data does not change past scores
- [ ] Holdout report generated (rank corr, precision@k) into docs/analytics/validation.md — real numbers, no invented accuracy
- [ ] Ground-truth emerging area ranks in top-k during its spike window
- [ ] LOW_CONFIDENCE tagging enforced

## Test Plan
Unit: scoring arithmetic. Validation: rolling holdout harness ({{RISK-003}} automates).

## Definition of Done
Standard DoD + model card (docs/analytics/model-cards/area-risk.md).

## Demo Evidence
D7: Peenya-like area HIGH with computed drivers; evidence drawer shows validation metrics.

## Limitations / Non-Goals
No causal claims; no individual scoring; synthetic-data caveat shipped.

## References
ADR-005; ADR-008; ADR-009.

=== ISSUE ===
key: RISK-003
title: [TEST] Risk validation suite (temporal holdout harness, leakage, reproducibility, driver integrity)
labels: type:test, area:risk, area:ml, priority:p0
milestone: M7
estimate: S
risk: LOW
blocked_by: RISK-002
--- BODY ---
## Summary
Automated harness: rolling temporal holdout evaluation, future-leakage detection, score reproducibility, driver-contribution integrity, ground-truth spike-area ranking.

## Acceptance Criteria
- [ ] Rolling holdout runs in CI (subset) producing metric artifacts
- [ ] Leakage mutation test green
- [ ] Identical inputs → identical scores
- [ ] Drivers recomputable from persisted features (integrity test)
- [ ] Ground-truth area in top-k during spike window

## Dependencies
Blocked by: {{RISK-002}} · Blocks: DoD of {{RISK-002}}

## Definition of Done
Green in CI; validation doc updated.

## References
{{RISK-002}}; DATA-001 ground truth.
