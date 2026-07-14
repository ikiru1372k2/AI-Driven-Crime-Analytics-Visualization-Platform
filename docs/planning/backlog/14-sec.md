=== ISSUE ===
key: EPIC-SEC
title: [EPIC] Security, Scope Enforcement & Governance
labels: type:epic, area:security, priority:p0
milestone: M9
estimate: -
risk: MEDIUM
blocked_by:
--- BODY ---
## Problem
Crime data is sensitive: victim/complainant PII, protected demographics, accused records. Authorization must be enforced server-side (client filters are cosmetic); PII must be minimized in analytics surfaces; misuse of demographics must be structurally prevented.

## Why it matters
A single scope-bypass or PII leak discredits the whole platform in judge review; governance is part of the challenge's SCRB reality.

## Technical scope
Server-side district/unit scoping, PII minimization in responses/logs, security test suite.

## Out of scope
AuthN ({{CAT-003}}), audit ({{PROV-003}}).

## Source data
Unit/District hierarchy (scope), all person tables (minimization targets).

## Catalyst services
Authentication, API Gateway, Data Store.

## Deliverables & success criteria
Scope-bypass attempts fail with tests proving it; no names in aggregates/logs; ADR-009 prohibitions enforced in CI.

## Risks
Scope logic scattered → single enforcement layer in repositories.

## Demo impact
Role-switch demo moment; judge Q&A resilience.

## Child issues
{{SEC-001}}, {{SEC-002}}, {{SEC-003}}

=== ISSUE ===
key: SEC-001
title: [SECURITY] Server-side district/unit data scoping enforced at repository layer
labels: type:security, area:security, area:auth, priority:p0
milestone: M9
estimate: M
risk: MEDIUM
blocked_by: CAT-003, ER-005
--- BODY ---
## Summary
Enforce AuthContext scope (STATE / DISTRICT(id) / UNIT(id)) inside the repository/query layer for every data access path — case queries, analytics results, evidence, graph, candidates — so no handler can accidentally return out-of-scope rows; scope resolution uses the Unit→District hierarchy ({{ER-005}} resolver).

## Problem Statement
Example threat: DISTRICT_ANALYST (DistrictID 44) requests statewide hotspots or another district's evidence case IDs. Post-filtering in handlers is error-prone; enforcement must be structural (scoped repository API where unscoped access requires an explicit privileged call, auditable).

## Source Data / ER Schema Mapping
Scope join: CaseMaster.PoliceStationID → Unit.UnitID → Unit.DistrictID (OBSERVED). Derived results scoped via their scope columns / evidence case joins.

## Catalyst Services
Data Store (scoped queries), Authentication.

## Dependencies
Blocked by: {{CAT-003}}, {{ER-005}} · Blocks: {{HOT-003}} finalization, {{GRAPH-003}}, {{ENT-003}}, {{SEC-003}}

## Technical Design
`ScopedRepository` base requiring AuthContext; unscoped access only via `system_context()` (jobs) — never constructible from request input; scope predicate pushed into queries (not post-filter); cross-scope aggregate policy: state-level FACT aggregates visible to all roles, record-level detail scoped (documented matrix per endpoint).

## Edge Cases
Case with null PoliceStationID (scoped OUT of district views, visible to STATE with quality flag); unit moved between districts (current hierarchy governs — documented); evidence lists crossing scopes (redact to counts for out-of-scope IDs).

## Acceptance Criteria
- [ ] Two-role integration matrix: district user vs state user across all list/detail endpoints — zero out-of-scope rows
- [ ] Handler cannot obtain unscoped repository from request context (type-level/test enforcement)
- [ ] Evidence redaction for out-of-scope case IDs proven
- [ ] Client-supplied scope params never widen access (fuzz test)

## Test Plan
Authz integration matrix; negative fuzz (tampered params/JWT claims); unit tests on predicate builder.

## Definition of Done
Standard DoD + endpoint scope matrix doc.

## Demo Evidence
Live role switch shows scoped views.

## Limitations / Non-Goals
Row-level encryption; court-order style access flows.

## References
{{CAT-003}}; {{ER-005}}; ADR-009.

=== ISSUE ===
key: SEC-002
title: [SECURITY] PII minimization in analytics responses, exports and logs
labels: type:security, area:security, priority:p0
milestone: M9
estimate: S
risk: LOW
blocked_by: PROV-002, HOT-003
--- BODY ---
## Summary
Systematic minimization: victim/complainant names and narratives excluded from all aggregate/state-level responses; case-detail PII visible only in scoped detail views (audited per {{PROV-003}}); structured logging with PII-denylist; error responses never echo record content.

## Problem Statement
Analytics surfaces aggregate thousands of person records; a single name in a state dashboard, log line, or stack trace is a governance failure.

## Technical Design
Response serializers with explicit field allowlists per endpoint class (aggregate vs detail); logging filter (denylist: name fields, BriefFacts) with unit tests; exception handler sanitization; export paths (future SmartBrowz) inherit allowlists.

## Dependencies
Blocked by: {{PROV-002}}, {{HOT-003}} · Blocks: {{SEC-003}}

## Acceptance Criteria
- [ ] Serializer allowlist tests per endpoint class (aggregate responses contain zero name/narrative fields — schema-level assertion)
- [ ] Log-capture test: request paths handling PII produce no PII in logs
- [ ] Forced exception does not leak record content
- [ ] Detail-view PII access audited

## Test Plan
Contract tests + log-capture harness + exception injection.

## Definition of Done
Standard DoD.

## Demo Evidence
Judge Q&A: show state dashboard payloads.

## References
ADR-009; {{PROV-003}}.

=== ISSUE ===
key: SEC-003
title: [TEST] Security test suite: scope bypass, injection, authz matrix, leakage
labels: type:test, area:security, priority:p1
milestone: M9
estimate: S
risk: LOW
blocked_by: SEC-001, SEC-002
--- BODY ---
## Summary
Consolidated security regression suite: authz matrix across roles×endpoints, scope-tamper fuzzing, ZCQL/query injection attempts through filter params, PII leakage scans on responses/logs, token forgery/expiry paths.

## Acceptance Criteria
- [ ] Role×endpoint matrix generated and asserted (any new endpoint without matrix entry fails CI)
- [ ] Injection fixtures (quotes, ZCQL metachars in filters) return 422/safe results
- [ ] Automated PII scan over recorded responses of full test run — zero hits outside allowlisted detail views
- [ ] Runs in CI

## Dependencies
Blocked by: {{SEC-001}}, {{SEC-002}}

## Definition of Done
Green in CI; findings log (empty or fixed).

## Demo Evidence
Cited under security questioning.

## References
{{SEC-001}} matrix.
