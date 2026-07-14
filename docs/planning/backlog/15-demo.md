=== ISSUE ===
key: EPIC-DEMO
title: [EPIC] Competition Demo Reliability & Submission
labels: type:epic, area:demo, priority:p0
milestone: M10
estimate: -
risk: MEDIUM
blocked_by:
--- BODY ---
## Problem
The five-minute judge demo must not depend on luck: deterministic data, rehearsed route, environment health checks, fallbacks, and a submission package (README, model cards, limitations, deployment verification).

## Why it matters
Story L: judges see DETECT→UNDERSTAND→CONNECT→RESOLVE→FLAG→FORECAST→EXPLAIN with evidence at every step — reliably.

## Technical scope
Deterministic seed+reset, demo route documentation with expected outputs, health checks + fallbacks + backup evidence, submission docs, final deployment verification.

## Constraint (ADR-011)
Analytics must calculate demo outputs; seed data may embed genuine statistical patterns; direct insertion of alerts/results is prohibited.

## Catalyst services
All deployed services; SmartBrowz optional for PDF intelligence report backup.

## Deliverables & success criteria
Reset→demo→reset reproducible; expected-output doc matches live results; deployment URL verified from clean network.

## Risks
Live network/QuickML latency → cached fallbacks + backup artifacts.

## Demo impact
Everything.

## Child issues
{{DEMO-001}}, {{DEMO-002}}, {{DEMO-003}}, {{DEMO-004}}, {{DEMO-005}}

=== ISSUE ===
key: DEMO-001
title: [FEATURE] Deterministic demo seed + reset procedure
labels: type:feature, area:demo, priority:p0
milestone: M10
estimate: M
risk: LOW
blocked_by: DATA-001, DATA-002
--- BODY ---
## Summary
One-command demo environment preparation: reset derived tables, load the canonical seeded dataset ({{DATA-001}}), run the full engine suite in order (hotspot, trend, MO, graph, ER candidates, anomaly, risk), and verify resulting state against the expected-output manifest — leaving the environment in exact pre-demo state.

## Problem Statement
Demo state drifts as we develop and rehearse (reviews confirm candidates, alerts acknowledged). Reset must restore the precise starting state, including review queues, without hard-coding any analytical result.

## Technical Design
`scripts/demo/reset.sh`: truncate DERIVED tables only (source reload from canonical dataset), sequenced engine runs with run-registry verification, final assertion pass against `docs/demo/expected-outputs.md` machine-readable companion (counts, alert presence, top candidate pair, risk top-k). Aborts loudly on any mismatch.

## ER Conformance Requirements
Source tables reloaded byte-identically; no result inserted directly (engine-only writes verified by provenance: every result row must have a run_id from this reset's runs).

## Dependencies
Blocked by: {{DATA-001}}, {{DATA-002}} + all engine issues (executes them) · Blocks: {{DEMO-002}}, {{DEMO-005}}

## Edge Cases
Partial engine failure mid-reset (abort with state report, safe to re-run); Catalyst rate limits during reload (chunked, resumable).

## Acceptance Criteria
- [ ] Two consecutive resets produce identical verification manifests
- [ ] Post-reset: ground-truth alert ACTIVE, hotspot present, MO profiles extracted, candidate queue populated PENDING_REVIEW, anomaly flagged, risk scores present
- [ ] Zero derived rows without a run_id from the reset sequence (no smuggled results)
- [ ] Runtime documented (target < 20 min)

## Test Plan
Full reset twice in dev env; manifest diff empty.

## Definition of Done
Standard DoD.

## Demo Evidence
Pre-demo checklist step 1.

## Limitations / Non-Goals
Not a production data-ops tool.

## References
ADR-011; DATA-001 ground truth.

=== ISSUE ===
key: DEMO-002
title: [DOCS] Five-minute demo route + expected analytics outputs document
labels: type:docs, area:demo, priority:p0
milestone: M10
estimate: S
risk: LOW
blocked_by: DEMO-001, UI-002, UI-003
--- BODY ---
## Summary
Scripted demo route with timings, exact clicks, expected on-screen values (from reset manifest), narration lines for each step D1–D9, judge-question appendix (where's the evidence? why this alert? how validated?) with the artifact answering each.

## Route (target 5:00)
D1 overview alert (0:00–0:40) → D2 map drill to cluster (–1:30) → D3 MO extraction card (–2:10) → D4 association graph (–2:50) → D5 identity candidate + confirm (–3:30) → D6 anomaly call-out (–3:55) → D7 risk drivers (–4:25) → D8 evidence drawer recap (–4:45) → D9 live FIR insert → alert update (–5:00, optional if EVT-002 shipped).

## Dependencies
Blocked by: {{DEMO-001}}, {{UI-002}}, {{UI-003}} · Related: all UI issues · Blocks: {{DEMO-005}}

## Acceptance Criteria
- [ ] Route rehearsed end-to-end ≤ 5:30 with expected values matching live screens
- [ ] Every step lists its evidence artifact (run_id path)
- [ ] Judge Q&A appendix covers: validation, false positives, PII, PersonID semantics, Catalyst usage, causation wording
- [ ] Fallback branches noted per step (from {{DEMO-003}})

## Definition of Done
Doc merged + rehearsal log.

## Demo Evidence
Is the demo.

## References
challenge-traceability.yaml demo_steps.

=== ISSUE ===
key: DEMO-003
title: [ENGINEERING] Environment health checks, fallbacks and backup evidence
labels: type:engineering, area:demo, priority:p1
milestone: M10
estimate: S
risk: MEDIUM
blocked_by: CAT-005, CAT-006, EVT-002
--- BODY ---
## Summary
Pre-demo health check script (auth, Data Store, AppSail, QuickML, map assets, event pipeline, hosted SPA) + degradation fallbacks (cached last-good analytics with staleness banner; pre-generated SmartBrowz PDF intelligence report + screenshot deck as network-death backup).

## Catalyst Services
All deployed; SmartBrowz for the PDF backup artifact.

## Dependencies
Blocked by: {{CAT-005}}, {{CAT-006}}, {{EVT-002}} · Blocks: {{DEMO-005}}

## Acceptance Criteria
- [ ] `scripts/demo/healthcheck.sh` verifies every service with pass/fail summary
- [ ] Simulated QuickML outage: MO screens degrade to cached profiles with honest staleness note (not fake extraction)
- [ ] Backup PDF + screenshots generated from real post-reset state and stored (Stratus + local)
- [ ] Fallback drill rehearsed once

## Definition of Done
Standard DoD.

## Demo Evidence
Insurance policy.

## References
{{UI-010}}; {{DEMO-002}}.

=== ISSUE ===
key: DEMO-004
title: [DOCS] Submission package: README, model cards, limitations, Catalyst service map
labels: type:docs, area:demo, priority:p0
milestone: M10
estimate: M
risk: LOW
blocked_by: PROV-002
--- BODY ---
## Summary
Judge-facing documentation: submission README (product story, architecture, live URL, demo guide, setup), model cards for every engine (objective, data, method, params, validation results, limitations, failure modes), consolidated limitations document (synthetic data, language scope, correlation-not-causation, PersonID semantics), Catalyst service map with per-service justification, external-dependency justifications (map GeoJSON, OSS libraries).

## Dependencies
Blocked by: {{PROV-002}} (classification vocabulary) · Content-depends on engine issues as they land · Blocks: {{DEMO-005}}

## Acceptance Criteria
- [ ] README enables a judge to reach the live app and re-run the demo unaided
- [ ] Model card per engine (7) with REAL validation numbers from docs/analytics/validation.md — no invented accuracy
- [ ] Limitations doc covers all ADR-mandated caveats
- [ ] Catalyst map: every service → capability → integration point → source files
- [ ] Every external dependency has gap justification + fallback note

## Definition of Done
Docs merged; cross-links verified.

## Demo Evidence
The submission itself.

## References
All ADRs; challenge-traceability.yaml.

=== ISSUE ===
key: DEMO-005
title: [DEPLOYMENT] Final Catalyst deployment verification & competition readiness review
labels: type:deployment, area:demo, area:catalyst, priority:p0
milestone: M10
estimate: S
risk: MEDIUM
blocked_by: DEMO-002, DEMO-003, CAT-006
--- BODY ---
## Summary
Final gate: production Catalyst deployment of all components (Pipelines-driven where feasible), clean-network verification (fresh browser/profile, judge-like conditions), full demo rehearsal on production, readiness checklist sign-off (every P0 issue closed or explicitly waived with documented impact), submission form assets verified.

## Catalyst Services
Pipelines (CI/CD), all deployed services, Domain Mappings if custom domain used.

## Dependencies
Blocked by: {{DEMO-002}}, {{DEMO-003}}, {{CAT-006}} + all P0 issues

## Acceptance Criteria
- [ ] Deployed URL fully functional from clean environment (incognito, non-team network)
- [ ] Full demo rehearsal on production environment matches expected-output doc
- [ ] P0 closure audit: list generated from GitHub; open P0s = explicit documented waivers
- [ ] Pipelines (or documented deploy runbook) reproduces deployment from main
- [ ] Submission checklist (URL, repo, docs, video if required) complete

## Definition of Done
Sign-off recorded in issue comment with rehearsal evidence.

## Demo Evidence
Judge-ready platform.

## References
{{DEMO-002}}; delivery-plan.md.
