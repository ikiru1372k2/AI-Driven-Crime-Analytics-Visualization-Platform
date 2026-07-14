=== ISSUE ===
key: EPIC-EVT
title: [EPIC] Catalyst Event Orchestration
labels: type:epic, area:catalyst, priority:p1
milestone: M9
estimate: -
risk: HIGH
blocked_by:
--- BODY ---
## Problem
Intelligence must stay current without manual recomputation: new FIR data should trigger the analytical pipeline. This is also the clearest showcase of Catalyst-native architecture (Signals → Event Functions → Circuits → Push).

## Why it matters
C2-R12; the "why Catalyst" judge answer; demo step D9 (live FIR → alert update).

## Technical scope
Signals on Data Store insert, event function, Circuits orchestration of parallel analytics branches, scheduled recomputation (Cron), push notifications.

## Out of scope
Engines themselves (M4–M7).

## Catalyst services
Signals, Event Functions, Circuits, Cron, Push Notifications, (Mail optional).

## Deliverables & success criteria
Insert FIR → within documented latency, MO extraction + hotspot/trend recompute triggered → threshold evaluation → alert visible; failures land in a dead-letter/log path, never silent.

## Risks
HIGH: Signals/Circuits availability & event payload shape unverified until {{CAT-001}}; fallback = Cron-driven polling pipeline (documented, still Catalyst-native).

## Demo impact
D9 closing moment.

## Child issues
{{EVT-001}}, {{EVT-002}}, {{EVT-003}}, {{EVT-004}}

=== ISSUE ===
key: EVT-001
title: [FEATURE] Catalyst Signals + Event Function on new FIR insert
labels: type:feature, area:catalyst, priority:p1, risk:catalyst
milestone: M9
estimate: M
risk: HIGH
blocked_by: CAT-002, DATA-002
--- BODY ---
## Summary
Configure Catalyst Signals to emit on CaseMaster (and child-table) inserts; implement the Event Function that validates the new record (single-record path of DATA-002 validation) and enqueues the analysis request (invokes {{EVT-002}} circuit or fallback dispatcher).

## Problem Statement
Today analytics only runs batch. The event entry point is missing; without validated single-record ingestion, event-driven analytics would process garbage.

## Source Data / ER Schema Mapping
CaseMaster insert payload (OBSERVED) — field parity validated against schema manifest before dispatch.

## Catalyst Services
Signals (event source), Event Functions (handler), Data Store.

## Dependencies
Blocked by: {{CAT-002}}, {{DATA-002}} · Blocks: {{EVT-002}}

## Technical Design
Signal → event function (thin, per ADR-010): manifest validation → provenance note (event received) → dispatch. Failure path: invalid record → quarantine log + data-quality counter; no partial analytics. Idempotency: event dedup by CaseMasterID+revision.

## Edge Cases
Bulk ingestion storms (batch load suppresses per-row events or coalesces — documented switch); out-of-order child inserts (accused arrives after case — dispatch waits/settles per documented debounce); replay/duplicate events.

## Acceptance Criteria
- [ ] Inserting a valid FIR via API/console fires the function (evidenced by log + provenance note) exactly once per record
- [ ] Invalid record quarantined, counted, no analytics dispatched
- [ ] Bulk-load mode does not stampede events (test with 100-row load)
- [ ] Availability findings + any fallback documented from {{CAT-001}} report

## Test Plan
Integration in dev environment (transcript committed); unit for validation/dedup with mocked payloads.

## Definition of Done
Standard DoD + capability citation.

## Demo Evidence
D9 insert → visible trigger log.

## Limitations / Non-Goals
Orchestration ({{EVT-002}}).

## References
ADR-010; {{CAT-001}}.

=== ISSUE ===
key: EVT-002
title: [FEATURE] Catalyst Circuits orchestration: parallel analysis branches + aggregation + threshold evaluation
labels: type:feature, area:catalyst, priority:p1, risk:catalyst
milestone: M9
estimate: M
risk: HIGH
blocked_by: EVT-001, HOT-002, TREND-002, MO-002
--- BODY ---
## Summary
Circuits workflow for a new FIR: parallel branches (A: MO extraction {{MO-002}} single-case; B: scoped hotspot refresh {{HOT-002}}; C: entity candidate generation for its accused {{ENT-001}} incremental; D: anomaly feature prep) → aggregation → trend/risk delta evaluation → alert creation ({{TREND-002}} path) → notification handoff ({{EVT-004}}).

## Problem Statement
Sequential recompute is slow and hides the platform's orchestration story; parallel branches with real aggregation demonstrate Circuits meaningfully — but only if Circuits actually supports the shape (verify first, per mandate).

## Catalyst Services
Circuits (orchestration), Functions (steps invoking AppSail endpoints), Data Store.

## Dependencies
Blocked by: {{EVT-001}}, {{HOT-002}}, {{TREND-002}}, {{MO-002}} · Related: {{ENT-001}} · Blocks: {{EVT-004}}, {{DEMO-003}}

## Technical Design
Circuit definition committed to repo; steps are thin function wrappers calling AppSail endpoints (scoped, incremental modes); branch failure isolates (MO failure doesn't block hotspot refresh) with aggregated status; all runs registered in IntelligenceRun with trigger=EVENT. Fallback (if Circuits unavailable per {{CAT-001}}): event function dispatches branches sequentially/async with same isolation semantics — same API surface, documented.

## Edge Cases
Partial branch failure; duplicate circuit execution (idempotent by case+revision); latency budget (document p95 event→alert).

## Acceptance Criteria
- [ ] New ground-truth-spike FIR insert results in updated trend evaluation and (when threshold crossed) an ACTIVE alert without manual action
- [ ] Branch failure isolation proven (kill MO branch → others complete, status reflects partial)
- [ ] Circuit/fallback definition reproducible from repo
- [ ] End-to-end latency documented

## Test Plan
Integration in dev env with instrumented run; failure injection.

## Definition of Done
Standard DoD + fallback decision recorded.

## Demo Evidence
D9: live insert → alert appears.

## Limitations / Non-Goals
Full statewide recompute on every event (scoped/incremental only; full recompute is {{EVT-003}}).

## References
{{CAT-001}}; ADR-010.

=== ISSUE ===
key: EVT-003
title: [FEATURE] Scheduled analytics recomputation via Catalyst Cron
labels: type:feature, area:catalyst, priority:p1
milestone: M9
estimate: S
risk: LOW
blocked_by: CAT-005, HOT-002, TREND-002
--- BODY ---
## Summary
Catalyst Cron jobs for full recomputation: nightly hotspot runs (both modes), trend evaluation, graph re-projection, risk refresh — each invoking AppSail job endpoints, registering IntelligenceRun with trigger=SCHEDULED, with overlap protection.

## Catalyst Services
Cron / Job Scheduling; AppSail.

## Dependencies
Blocked by: {{CAT-005}}, {{HOT-002}}, {{TREND-002}} · Related: {{GRAPH-001}}, {{RISK-002}}

## Edge Cases
Job overlap (skip-if-running lock); partial failure resumability; schedule timezone (IST documented).

## Acceptance Criteria
- [ ] Configured schedules committed/reproducible; manual trigger path for demo
- [ ] Overlap lock proven (concurrent trigger → second skips with log)
- [ ] Each job produces IntelligenceRun rows with trigger=SCHEDULED
- [ ] Failure alerting: failed run visible in ops status endpoint

## Definition of Done
Standard DoD.

## Demo Evidence
Run history panel shows scheduled runs.

## References
ADR-010.

=== ISSUE ===
key: EVT-004
title: [FEATURE] Push notifications for high-severity alerts
labels: type:feature, area:catalyst, priority:p2
milestone: M9
estimate: S
risk: MEDIUM
blocked_by: EVT-002, CAT-003
--- BODY ---
## Summary
Catalyst Push Notifications (web) for newly ACTIVE high-severity trend alerts to opted-in, scope-matching users; notification carries alert deep link; no PII in payload.

## Catalyst Services
Push Notifications; Authentication (user targeting).

## Dependencies
Blocked by: {{EVT-002}}, {{CAT-003}}

## Acceptance Criteria
- [ ] High-severity alert triggers push to opted-in state-scope user (dev-env proof)
- [ ] District-scoped user not notified for other districts
- [ ] Payload = region/category/severity + link only (no names/narratives)
- [ ] Opt-in/out persisted

## Definition of Done
Standard DoD; if web push unsupported in environment, Mail fallback documented + implemented.

## Demo Evidence
Optional D9 flourish.

## References
{{TREND-002}}; {{CAT-001}} report.
