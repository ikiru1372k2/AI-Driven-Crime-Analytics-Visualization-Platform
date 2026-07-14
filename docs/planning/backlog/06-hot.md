=== ISSUE ===
key: EPIC-HOT
title: [EPIC] Spatiotemporal Hotspot Analytics
labels: type:epic, area:hotspot, area:analytics, priority:p0
milestone: M4
estimate: -
risk: MEDIUM
blocked_by:
--- BODY ---
## Problem
SCRB cannot see where and when crime concentrates. CaseMaster carries coordinates and occurrence times, but nothing projects them into defensible spatial/spatiotemporal clusters.

## Why it matters
"Spatiotemporal Clusters / Crime Hotspots by layering time of day with location" is an explicit challenge capability (C2-R3) and the demo's first wow moment (D2).

## Challenge requirement
C2-R3; feeds C2-R9 (risk features).

## Technical scope
Feature pipeline (validated coords + cyclic time), clustering engine (DBSCAN/HDBSCAN + KDE density), evidence persistence, scoped API, validation suite.

## Out of scope
Trend baselines ({{EPIC-TREND}}), map UI ({{UI-002}}), risk scoring ({{EPIC-RISK}}).

## Source data
CaseMaster: IncidentFromDate, IncidentToDate, latitude, longitude, CrimeMajorHeadID, CrimeMinorHeadID, PoliceStationID (all OBSERVED).

## Catalyst services
Data Store, AppSail, Cron (scheduled recompute via {{EVT-003}}).

## Deliverables & success criteria
Known synthetic cluster discovered with correct evidence case IDs; midnight-proximity encoding validated; no output without method version + evidence.

## Risks
Parameter sensitivity (eps/min_samples) — versioned parameter strategy + stability checks.

## Demo impact
D2 — pulsing hotspot on the Karnataka map backed by real clustering.

## Child issues
{{HOT-001}}, {{HOT-002}}, {{HOT-003}}, {{HOT-004}}

=== ISSUE ===
key: HOT-001
title: [FEATURE] Spatiotemporal feature pipeline: validated coordinates + cyclic temporal encoding
labels: type:feature, area:hotspot, area:analytics, priority:p0
milestone: M4
estimate: M
risk: LOW
blocked_by: DATA-002, ER-002
--- BODY ---
## Summary
Transform eligible CaseMaster records into a normalized spatiotemporal feature set: validated lat/long, occurrence timestamp policy, cyclic hour-of-day and day-of-week encodings (sin/cos), category/station context — with exclusion accounting for ineligible records.

## Problem Statement
CaseMaster contains incident coordinates and timestamps, but no normalized feature projection exists. Clustering cannot treat raw hour values linearly (23:59 and 00:01 are close); records with missing/invalid coordinates must be excluded transparently, not silently.

## Why This Matters
Every spatial engine (HOT-002, ANOM-001 location context, RISK-001 density) consumes these features; correctness here is inherited everywhere.

## Engineering Objective
`kavach/analytics/hotspot/features.py` producing `SpatioTemporalFeature` rows keyed by CaseMasterID.

## Source Data / ER Schema Mapping (OBSERVED → DERIVED)
```
CaseMaster.latitude/longitude → validated lat/long (Karnataka bbox + not-null + numeric)
CaseMaster.IncidentFromDate   → occurrence_ts (policy: IncidentFromDate; if null → EXCLUDE, never substitute CrimeRegisteredDate)
occurrence_ts → incident_hour → hour_sin=sin(2π·h/24), hour_cos=cos(2π·h/24)
occurrence_ts → dow → dow_sin/dow_cos (period 7)
CaseMaster.CrimeMajorHeadID/CrimeMinorHeadID/PoliceStationID → context (label/filter fields, not distance dimensions by default)
```
Features are DERIVED; lineage documented per matrix §5.

## ER Conformance Requirements
- IncidentFromDate is the sole occurrence-time source (never CrimeRegisteredDate)
- Coordinates never imputed/synthesized in production paths
- Exclusions counted per reason: null_coords, invalid_coords, out_of_bounds, null_occurrence_ts

## Catalyst Services
Data Store (read via repositories); runs in AppSail.

## Dependencies
Blocked by: {{DATA-002}}, {{ER-002}} · Blocks: {{HOT-002}}, {{ANOM-001}}, {{RISK-001}}

## Algorithm / Analytical Method
Objective: eligible-record projection. Preprocessing: bbox validation (Karnataka approx lat 11.5–18.5, lon 74.0–78.6, constants versioned), timezone-consistent hour extraction. Failure conditions: >X% exclusions → pipeline warns (data-quality signal). Limitations: multi-day incidents use IncidentFromDate hour; documented.

## Edge Cases
Midnight boundary (23:59 vs 00:01 → cyclic distance small — explicit test); incident spanning dates; lat/long swapped (out-of-bbox → excluded+counted); duplicate CaseMasterID (upstream error, assert); 0.0/0.0 coordinates (invalid).

## Acceptance Criteria
- [ ] Given valid records, every feature row is traceable to a CaseMasterID
- [ ] Given null latitude, record excluded and counted under null_coords
- [ ] Given 23:59 and 00:01 incidents, Euclidean distance over (hour_sin,hour_cos) < distance for 12h separation (test)
- [ ] Exclusion metrics persisted with run and retrievable
- [ ] Deterministic output for fixed input

## Test Plan
Unit: encodings, bbox, exclusions. Property: cyclic distance monotonicity. Integration: full synthetic dataset run with expected eligible count (from DATA-001 rates).

## Observability
Feature run logs: eligible/excluded counts by reason; run_id linkage.

## Definition of Done
Standard DoD + ER gate pass + lineage doc.

## Demo Evidence
Data-quality panel: "N analysed, M excluded (missing coordinates)".

## Limitations / Non-Goals
No clustering (HOT-002); no H3 aggregation unless HOT-002 requires it.

## References
Matrix §1.1/§5; ADR-008.

=== ISSUE ===
key: HOT-002
title: [FEATURE] Hotspot detection engine: DBSCAN/HDBSCAN spatial + spatiotemporal clustering with KDE density and evidence output
labels: type:feature, area:hotspot, area:analytics, area:ml, priority:p0, risk:model
milestone: M4
estimate: L
risk: MEDIUM
blocked_by: HOT-001, PROV-001
--- BODY ---
## Summary
Detect spatial and spatiotemporal crime clusters over the feature set: haversine-metric DBSCAN (and HDBSCAN if runtime supports) for cluster discovery, optional cyclic-time dimensions for spatiotemporal mode, KDE-based density surface for map heat, persisted as HotspotResult rows through the provenance framework with full evidence case IDs.

## Problem Statement
With features available (HOT-001) there is still no defensible cluster: no algorithm, parameters, versioning, or evidence chain. A pulsing map zone without a statistical basis is prohibited.

## Why This Matters
Core challenge capability (C2-R3); direct input to risk (cluster density/growth) and the flagship demo step.

## User Story
As an SCRB analyst, I want statistically derived crime clusters by area/time/category, so that I can direct review to genuine concentrations instead of anecdotes.

## Source Data / ER Schema Mapping
Input: SpatioTemporalFeature (DERIVED from CaseMaster per HOT-001). Filters: CrimeMajorHeadID/CrimeMinorHeadID, PoliceStationID→district scope (OBSERVED context). Output: HotspotResult (DERIVED, classification STATISTICAL_INFERENCE).

## Catalyst Services
AppSail (compute), Data Store (results), Cron via {{EVT-003}} for scheduled recompute.

## Dependencies
Blocked by: {{HOT-001}}, {{PROV-001}} · Blocks: {{HOT-003}}, {{HOT-004}}, {{RISK-001}}, {{EVT-002}}

## Algorithm / Analytical Method
- Objective: density-based clusters robust to noise; no fixed cluster count
- Spatial mode: DBSCAN, haversine metric on radians, eps in meters (default 500m urban, parameter set versioned `hotspot-params v1`), min_samples default 5
- Spatiotemporal mode: feature vector [scaled_lat, scaled_lon, w_t·hour_sin, w_t·hour_cos]; scaling strategy documented (meters-equivalent scaling; w_t versioned); HDBSCAN preferred if available for variable density
- Density surface: gaussian KDE over cluster region for heat rendering (grid resolution versioned)
- Per cluster outputs: centroid, radius (p90 member distance), member count, case IDs, dominant category distribution, time-window profile (hour histogram), density score
- Validation: against DATA-001 ground truth (HOT-004); stability: ±10% eps must retain ≥80% membership of ground-truth cluster (documented, tested)
- Failure conditions: <min eligible records → run completes with "insufficient data" state, no clusters
- Limitations: urban density bias (documented); eps global per run (no adaptive eps in v1)

## Persistence Design
HotspotResult: hotspot_id, run_id, mode (SPATIAL|SPATIOTEMPORAL), centroid_lat/lon, radius_m, case_count, category_summary JSON, hour_profile JSON, density_score, params_version. Evidence row: evidence_case_ids = member CaseMasterIDs.

## Security & Privacy
Results carry case IDs only (no names); scope filtering applied at API layer ({{HOT-003}}/{{SEC-001}}).

## Edge Cases
All-noise datasets (zero clusters is a valid, persisted outcome); single dense mega-cluster; clusters straddling district borders (assigned by centroid, membership preserved); duplicate coordinates (station-address geocoding artifacts) — documented as density inflation limitation.

## Acceptance Criteria
- [ ] Ground-truth synthetic cluster discovered with ≥90% of its member case IDs (HOT-004 automates)
- [ ] Uniform-random control region produces no cluster (noise test)
- [ ] Spatiotemporal mode separates same-location/different-time-window patterns (test fixture)
- [ ] Every persisted hotspot has run_id, params_version, non-empty evidence_case_ids
- [ ] Re-run on identical data yields identical clusters (deterministic seed/config)

## Test Plan
Unit: metric/scaling math. Analytics validation: ground-truth discovery, noise, stability (in {{HOT-004}}). Integration: full pipeline run persisting via PROV SDK.

## Observability
Run logs: record counts, cluster count, params version, wall time.

## Definition of Done
Standard DoD + ER gate + HOT-004 suite green + no placeholder outputs.

## Demo Evidence
Peenya-like cluster on map; click → member case count + evidence IDs matching ground truth.

## Limitations / Non-Goals
No forecasting (RISK-002); no automatic parameter tuning UI.

## References
ADR-008; {{HOT-001}}; DATA-001 ground truth.

=== ISSUE ===
key: HOT-003
title: [FEATURE] Hotspot API: scoped retrieval, filters, drill-down aggregates
labels: type:feature, area:hotspot, priority:p0
milestone: M4
estimate: S
risk: LOW
blocked_by: HOT-002, CAT-003
--- BODY ---
## Summary
REST endpoints exposing hotspot results and drill-down aggregates with server-side scope enforcement and classification envelope.

## API Contract
- `GET /api/v1/hotspots?mode=&district_id=&unit_id=&category_id=&window=` → latest completed run's clusters (envelope: STATISTICAL_INFERENCE, method version, evidence ref)
- `GET /api/v1/hotspots/{hotspot_id}` → detail incl. evidence_case_ids (scope-checked)
- `GET /api/v1/aggregates/cases?group_by=district|unit|category&window=` → drill-down counts (FACT classification)
- Auth: Catalyst token required; scope from AuthContext (STATE sees all; DISTRICT limited — enforced in query, not post-filter)
- Errors: 401/403/422 envelope; pagination on detail case lists

## Source Data / ER Schema Mapping
HotspotResult + IntelligenceEvidence (DERIVED); aggregates from CaseMaster joined Unit/District (OBSERVED).

## Dependencies
Blocked by: {{HOT-002}}, {{CAT-003}} · Blocks: {{UI-002}}, {{UI-003}}, {{SEC-002}}

## Security & Privacy
No person names in any response; district analyst requesting other district → 403 (test); evidence lists capped with pagination.

## Edge Cases
No completed run yet (empty-with-status, not 500); stale run (age surfaced); huge evidence lists.

## Acceptance Criteria
- [ ] District-scoped user receives only own-district hotspots (integration test with two roles)
- [ ] Response envelope carries classification + method_version + run age
- [ ] Contract tests green; OpenAPI published
- [ ] p95 latency < 500ms on synthetic dataset

## Test Plan
Contract + authz integration tests; latency smoke.

## Definition of Done
Standard DoD.

## Demo Evidence
Map layer + drill-down powered by these endpoints.

## Limitations / Non-Goals
UI (UI-002); trend deltas (TREND APIs).

## References
{{PROV-002}}; {{SEC-001}}.

=== ISSUE ===
key: HOT-004
title: [TEST] Hotspot analytics validation suite (ground truth, noise, midnight, stability)
labels: type:test, area:hotspot, area:ml, priority:p0
milestone: M4
estimate: M
risk: LOW
blocked_by: HOT-002, DATA-001
--- BODY ---
## Summary
Automated validation for the hotspot engine against DATA-001 ground truth: known-cluster discovery, no-false-cluster noise control, midnight temporal proximity, coordinate exclusion accounting, and parameter stability.

## Problem Statement
"The clustering works" is unverifiable without ground-truth tests; judges will ask how we know.

## Engineering Objective
`backend/tests/analytics/hotspot/` suite consuming `ground_truth.json` (test-only import path).

## Acceptance Criteria
- [ ] Ground-truth cluster recovered: ≥90% member recall, ≤10% impostor rate
- [ ] Uniform control region: zero clusters (or documented threshold)
- [ ] 23:59/00:01 fixture cases co-cluster in spatiotemporal mode; 12h-apart cases do not
- [ ] Exclusion counts equal DATA-001 documented missingness exactly
- [ ] eps ±10% retains ≥80% ground-truth membership (stability)
- [ ] Suite runs in CI

## Test Plan
This suite; runtime < 3 min.

## Dependencies
Blocked by: {{HOT-002}}, {{DATA-001}} · Blocks: DoD of {{HOT-002}} (gate)

## Definition of Done
Green in CI; results summarized in docs/analytics/validation.md.

## Demo Evidence
Validation summary cited when judges challenge the map.

## Limitations / Non-Goals
Real-data validation (no real data available — stated).

## References
DATA-001 ground truth; ADR-008.
