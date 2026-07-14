=== ISSUE ===
key: EPIC-TREND
title: [EPIC] Emerging Trend Detection
labels: type:epic, area:trends, area:analytics, priority:p0
milestone: M4
estimate: -
risk: LOW
blocked_by:
--- BODY ---
## Problem
SCRB cannot detect when a crime category in a region deviates from its historical baseline. Every "red-zone pulse" must be backed by a real statistical threshold — no fake alerts.

## Why it matters
C2-R4 is an explicit challenge capability with a named UI behavior (red-zone pulsing); it is also the demo's opening hook (D1).

## Challenge requirement
C2-R4; feeds C2-R9 (baseline-deviation risk feature).

## Technical scope
Robust baseline engine (rolling median/MAD, z-score, EWMA), alert generation with thresholds + evidence, validation suite.

## Out of scope
UI ({{UI-003}}/{{UI-004}}), push delivery ({{EVT-004}}).

## Source data
CaseMaster: IncidentFromDate (occurrence series), CrimeRegisteredDate (reporting series — separate, documented), CrimeMajorHeadID/CrimeMinorHeadID, PoliceStationID, District via Unit.

## Catalyst services
Data Store, AppSail, Cron; Signals/Circuits recompute path ({{EVT-002}}).

## Deliverables & success criteria
Known synthetic spike alerts; stable baseline produces zero alerts; sparse series reports insufficient-history instead of alerting.

## Risks
Threshold sensitivity → sensitivity documented in validation.

## Demo impact
D1 — the alert that starts the demo story.

## Child issues
{{TREND-001}}, {{TREND-002}}, {{TREND-003}}

=== ISSUE ===
key: TREND-001
title: [FEATURE] Baseline & deviation engine: rolling robust baselines, MAD z-scores, EWMA
labels: type:feature, area:trends, area:analytics, priority:p0
milestone: M4
estimate: M
risk: LOW
blocked_by: DATA-002
--- BODY ---
## Summary
Compute per-(scope × crime category × week) count series from CaseMaster and evaluate current-window deviation against a rolling robust baseline: median + MAD z-score primary, EWMA secondary signal, with explicit insufficient-history and sparse-series handling.

## Problem Statement
Raw counts exist but no baseline concept: "11 robberies this week" is meaningless without "baseline 4.2/week, MAD-z 3.1". Naive mean/std baselines break on sparse, skewed crime series.

## Why This Matters
The deviation quantity is the alert trigger (TREND-002) and a top risk feature (RISK-001).

## Engineering Objective
`kavach/analytics/trends/baseline.py` producing DeviationResult per series.

## Source Data / ER Schema Mapping (OBSERVED → DERIVED)
```
CaseMaster.IncidentFromDate → week bucket (occurrence series; policy consistent with HOT-001)
CaseMaster.CrimeMajorHeadID (and optional CrimeMinorHeadID) → category dimension
CaseMaster.PoliceStationID → Unit → District → scope dimension (station/district/state)
count(week, scope, category) → baseline_median, MAD, z = (current − median)/ (1.4826·MAD), EWMA(α versioned)
```

## ER Conformance Requirements
Occurrence vs registration series never mixed (both computable, labelled); IncidentFromDate nulls excluded + counted.

## Catalyst Services
Data Store (reads), AppSail.

## Dependencies
Blocked by: {{DATA-002}} · Blocks: {{TREND-002}}, {{RISK-001}}

## Algorithm / Analytical Method
Baseline window: trailing 26 weeks (versioned param), excluding current; min-history guard: ≥8 non-null weeks else INSUFFICIENT_HISTORY; MAD=0 handling (all-identical history): fall back to Poisson tail probability (documented); seasonality: day-of-week handled by weekly bucketing; STL deferred until real multi-year data exists (documented). Failure: empty series → no result, counted.

## Edge Cases
Zero-inflated series; brand-new station; week boundary/timezone; category with single historical burst (MAD robustness test); backfilled data changing history (recompute semantics documented).

## Acceptance Criteria
- [ ] Synthetic spike series yields z ≥ configured threshold; stable series |z| < 1 (fixtures)
- [ ] MAD=0 series handled without division error, via documented fallback
- [ ] <8-week series → INSUFFICIENT_HISTORY, never a score
- [ ] Deterministic outputs; params versioned (`trend-params v1`)

## Test Plan
Unit fixtures per edge case; property test: shifting a series by constant doesn't change z.

## Definition of Done
Standard DoD + lineage doc.

## Demo Evidence
"Current 11 vs baseline 4.2/week (MAD-z 3.1)" panel numbers come from here.

## Limitations / Non-Goals
No alert persistence (TREND-002); no change-point detection v1 (documented candidate).

## References
ADR-008.

=== ISSUE ===
key: TREND-002
title: [FEATURE] Emerging trend alert generation: thresholds, persistence, evidence
labels: type:feature, area:trends, priority:p0
milestone: M4
estimate: S
risk: LOW
blocked_by: TREND-001, PROV-001
--- BODY ---
## Summary
Convert deviation results into persisted TrendAlert records through the provenance framework: threshold policy, dedup/refresh semantics, full evidence (region, category, current, baseline, deviation, window, contributing case IDs), alert states.

## Problem Statement
Deviations are computed but nothing durable tells an analyst "robbery in Peenya is 2.6× baseline". Alerts must be evidence-backed and never duplicate-spam on recompute.

## User Story
As a supervisor, I want alerts when a category materially exceeds baseline, so that I prioritize review before manual reports surface it.

## Source Data / ER Schema Mapping
DeviationResult (DERIVED) + contributing CaseMasterIDs of the current window (OBSERVED refs). TrendAlert = DERIVED, classification STATISTICAL_INFERENCE.

## Catalyst Services
Data Store; AppSail; downstream Push via {{EVT-004}}.

## Dependencies
Blocked by: {{TREND-001}}, {{PROV-001}} · Blocks: {{UI-004}}, {{EVT-002}}, {{RISK-001}}, {{TREND-003}}

## Technical Design
Threshold policy v1: fire when z ≥ 2.5 AND current_count ≥ 5 (both versioned; documented rationale: statistical + material significance). States: ACTIVE → ACKNOWLEDGED → RESOLVED/EXPIRED. Refresh: same (scope, category) active alert updates in place with history, never duplicates. Persist via PROV SDK with factors: {current, baseline_median, mad_z, ewma_signal, window}.

## Edge Cases
Alert flapping near threshold (hysteresis: clear at z<1.5); scope hierarchy double-alert (district fires; station alert linked as child context, not separate top-level spam); INSUFFICIENT_HISTORY never alerts.

## Acceptance Criteria
- [ ] Synthetic spike produces exactly one ACTIVE alert with correct numbers + case IDs (ground truth)
- [ ] Recompute on unchanged data does not duplicate alerts
- [ ] Alert JSON includes region, category, current, baseline, deviation score, window, evidence ref
- [ ] Hysteresis behavior unit-tested

## Test Plan
Unit: threshold/hysteresis/dedup. Integration: end-to-end from dataset to persisted alert.

## Definition of Done
Standard DoD + no fake alerts possible (only engine-created).

## Demo Evidence
D1 alert card; evidence drawer shows method trend-params v1.

## Limitations / Non-Goals
Delivery channels (EVT-004); UI (UI-004).

## References
{{TREND-001}}; {{PROV-001}}.

=== ISSUE ===
key: TREND-003
title: [TEST] Trend detection validation suite (spike, stability, sparse, sensitivity)
labels: type:test, area:trends, area:ml, priority:p0
milestone: M4
estimate: S
risk: LOW
blocked_by: TREND-002, DATA-001
--- BODY ---
## Summary
Automated validation: ground-truth spike detected; stable baselines silent; sparse series refuse to alert; threshold sensitivity documented (alerts vs z-threshold curve on synthetic data).

## Acceptance Criteria
- [ ] DATA-001 embedded spike (window/category/station from ground_truth.json) produces the expected alert
- [ ] Stable control series across full dataset produce zero alerts
- [ ] Sparse/new-station series → INSUFFICIENT_HISTORY (no alert), asserted
- [ ] Sensitivity table (z∈{2.0,2.5,3.0} → alert counts) generated into docs/analytics/validation.md
- [ ] Suite in CI

## Dependencies
Blocked by: {{TREND-002}}, {{DATA-001}} · Blocks: DoD of {{TREND-002}}

## Definition of Done
Green in CI; validation doc updated.

## Demo Evidence
Cited when judges ask "would this spam alerts?"

## References
DATA-001 ground truth; ADR-008.
