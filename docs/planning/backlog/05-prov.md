=== ISSUE ===
key: EPIC-PROV
title: [EPIC] Intelligence Evidence & Provenance Framework
labels: type:epic, area:provenance, priority:p0
milestone: M3
estimate: -
risk: LOW
blocked_by:
--- BODY ---
## Problem
Explainability is a first-class product feature: every analytical output must answer what/where/when/which data/which method/why/which cases/limitations. Without a shared provenance framework each engine would invent its own, inconsistently.

## Why it matters
This is the platform's core differentiator ("evidence-backed" everywhere) and a hard dependency for every engine (C2-R11).

## Challenge requirement
C2-R11 (explainability), underpins R3–R10.

## Technical scope
IntelligenceRun + IntelligenceEvidence model/persistence, classification enums + API envelope, audit logging for sensitive actions.

## Out of scope
Engine-specific factor calculations (each engine issue).

## Source data
References CaseMaster.CaseMasterID as universal evidence pointer; derived tables per derived-intelligence-schema.md.

## Catalyst services
Data Store.

## Deliverables & success criteria
{{PROV-001}} framework; {{PROV-002}} classification + envelope; {{PROV-003}} audit log. Success: no engine can persist a result without run/method/evidence.

## Risks
Low; design already specified in derived-intelligence-schema.md.

## Demo impact
Evidence drawer (D8) — the recurring "wow, they can prove it" moment.

## Child issues
{{PROV-001}}, {{PROV-002}}, {{PROV-003}}

=== ISSUE ===
key: PROV-001
title: [FEATURE] IntelligenceRun + IntelligenceEvidence framework (model, persistence, engine SDK)
labels: type:feature, area:provenance, priority:p0
milestone: M3
estimate: M
risk: LOW
blocked_by: ER-002, CAT-002
--- BODY ---
## Summary
Implement the provenance core per derived-intelligence-schema.md: `IntelligenceRun` (type, method+version, model version, window, scope, status) and `IntelligenceEvidence` (evidence_case_ids, factors, limitations, classification), plus a small engine-facing SDK (`with intelligence_run(...) as run: run.emit(result, evidence)`) so engines cannot bypass provenance.

## Problem Statement
Engines are about to be built in parallel (hotspot, trend, MO…). Without a shared, enforced provenance write-path, evidence becomes optional and inconsistent — exactly the "unexplained 94% anomaly" failure the product forbids.

## Why This Matters
Blocks HOT-002, TREND-002, MO-003, GRAPH-001, ANOM-002, RISK-002. The evidence drawer (UI-009) renders this data.

## Engineering Objective
`backend/kavach/provenance/` with models, repository, context-manager SDK, and failure semantics (run marked FAILED with error on exception).

## Source Data / ER Schema Mapping
evidence_case_ids reference CaseMaster.CaseMasterID (OBSERVED). All framework tables are DERIVED (boundary doc).

## ER Conformance Requirements
Derived tables never mutate source tables; classification enum mandatory on every evidence row.

## Catalyst Services
Data Store (IntelligenceRun, IntelligenceEvidence tables from {{CAT-002}}).

## Dependencies
Blocked by: {{ER-002}}, {{CAT-002}} · Blocks: {{HOT-002}}, {{TREND-002}}, {{MO-003}}, {{GRAPH-001}}, {{ANOM-002}}, {{RISK-002}}, {{PROV-002}}

## Technical Design
- `IntelligenceType` enum: HOTSPOT | TREND_ALERT | MO_PROFILE | MO_SIMILARITY | ASSOCIATION | IDENTITY_CANDIDATE | ANOMALY | AREA_RISK
- Run lifecycle: RUNNING → COMPLETED/FAILED; generated_at server-side
- Evidence: result_ref, evidence_case_ids (non-empty for case-backed results), factors JSON {name, contribution, direction}, limitations list, classification enum
- SDK enforces: emit() without case IDs raises unless intelligence type is whitelisted as aggregate-only (documented)

## Edge Cases
Huge evidence lists (cap + "and N more" with full list retrievable); engine crash mid-run; concurrent runs of same type/scope (allowed, distinguished by run_id).

## Acceptance Criteria
- [ ] Engine cannot persist a result outside a run context (attempt raises, unit-tested)
- [ ] FAILED runs persist error and never leave partial COMPLETED evidence
- [ ] Every evidence row has classification + method version (DB-level not-null + tests)
- [ ] Query API: latest completed run per type/scope; evidence by result_ref

## Test Plan
Unit: lifecycle, enforcement, failure paths. Integration: round-trip vs Data Store dev env.

## Definition of Done
Standard DoD + boundary doc checklist items ticked (matrix §6 DERIVED item).

## Demo Evidence
Any evidence drawer entry shows run_id → method version → case IDs.

## Limitations / Non-Goals
UI (UI-009); engine factor semantics (per engine).

## References
derived-intelligence-schema.md; ADR-009.

=== ISSUE ===
key: PROV-002
title: [FEATURE] Data classification enums + API response envelope (FACT / AI_DERIVED / …)
labels: type:feature, area:provenance, priority:p0
milestone: M3
estimate: S
risk: LOW
blocked_by: PROV-001
--- BODY ---
## Summary
Standardize the six-class data classification (FACT, DERIVED_METRIC, STATISTICAL_INFERENCE, AI_DERIVED, POTENTIAL_ASSOCIATION, HUMAN_CONFIRMED) across all API responses via a shared envelope: every intelligence payload field group carries its classification, method/model version and evidence pointer.

## Problem Statement
The UI must visually differentiate observed fact from AI inference (challenge-critical). That's impossible unless APIs consistently transmit classification metadata.

## Engineering Objective
`ClassifiedValue`/`IntelligencePayload` response schemas used by all analytics routers; serializer helpers; OpenAPI documented.

## Catalyst Services
None new (rides AppSail APIs).

## Dependencies
Blocked by: {{PROV-001}} · Blocks: {{UI-001}} (labeling system), {{UI-009}}, {{SEC-002}}

## Acceptance Criteria
- [ ] Envelope schema documented in OpenAPI with examples per classification
- [ ] Lint/test asserts analytics responses use the envelope (router contract test)
- [ ] Classification is machine-readable AND human strings are centralized (i18n-ready)

## Test Plan
Contract tests per router (added as routers land); serializer unit tests.

## Definition of Done
Standard DoD.

## Demo Evidence
API response shown with classification fields; UI badges map 1:1.

## Limitations / Non-Goals
UI rendering (UI-001/UI-009).

## References
derived-intelligence-schema.md; ADR-009.

=== ISSUE ===
key: PROV-003
title: [FEATURE] Audit logging for sensitive actions (identity review, sensitive access, report generation)
labels: type:feature, area:provenance, area:security, priority:p1
milestone: M3
estimate: S
risk: LOW
blocked_by: CAT-003, PROV-001
--- BODY ---
## Summary
Append-only `AuditEvent` table + middleware/helpers recording: identity match review decisions, sensitive case-detail access (names visible), alert review actions, report generation — with actor, scope, timestamp, target refs.

## Problem Statement
High-value actions (confirming an identity match) are irreversible in intelligence terms and must be attributable; challenge governance expectations and ADR-004 require it.

## Engineering Objective
`kavach/provenance/audit.py` + decorators for route handlers.

## Source Data / ER Schema Mapping
Targets referenced by IDs (CaseMasterID, AccusedMasterID, candidate_id). DERIVED table.

## Catalyst Services
Data Store.

## Dependencies
Blocked by: {{CAT-003}}, {{PROV-001}} · Blocks: {{ENT-003}}

## Security & Privacy
Audit rows contain IDs, never names/narratives; no deletion API; access restricted to SYSTEM_ADMIN.

## Acceptance Criteria
- [ ] Identity review decision writes exactly one audit event with actor+decision+candidate_id (integration test)
- [ ] Case-detail access with PII visibility audited
- [ ] Audit query API scoped to SYSTEM_ADMIN
- [ ] No update/delete path exists for audit rows

## Test Plan
Unit + integration on decorated routes; authz test on query API.

## Definition of Done
Standard DoD.

## Demo Evidence
Admin audit view (or API output) after demo review action.

## Limitations / Non-Goals
SIEM export.

## References
ADR-004; {{ENT-003}}.
