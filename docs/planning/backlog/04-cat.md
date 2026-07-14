=== ISSUE ===
key: EPIC-CAT
title: [EPIC] Catalyst Platform Foundation
labels: type:epic, area:catalyst, priority:p0
milestone: M2
estimate: -
risk: HIGH
blocked_by:
--- BODY ---
## Problem
Deployment via Catalyst is mandatory and several Catalyst capabilities (QuickML surface, Circuits, Data Store limits) are unverified assumptions until a real project exists. Everything Catalyst-native flows through this epic.

## Why it matters
Submission validity (ADR-001). Early verification kills risk: if a service is unavailable, fallbacks must be designed in weeks, not hours.

## Challenge requirement
Mandatory Catalyst deployment; services table rows 1–26.

## Technical scope
Project init + credits, Data Store provisioning, Authentication + roles, API Gateway, AppSail runtime, Web Client Hosting.

## Out of scope
Signals/Circuits/Cron ({{EPIC-EVT}}), Pipelines ({{DEMO-005}}).

## Catalyst services
Data Store, Authentication, API Gateway, AppSail, Web Client Hosting, CLI.

## Deliverables & success criteria
Live Catalyst project; tables provisioned matching schema manifest; login works with role assignment; AppSail serves the API; SPA hosted.

## Risks
HIGH: account/credits (claim code KSPH26), service availability, runtime limits. Each verified and documented in {{CAT-001}}.

## Demo impact
The deployed URL judges open.

## Child issues
{{CAT-001}}, {{CAT-002}}, {{CAT-003}}, {{CAT-004}}, {{CAT-005}}, {{CAT-006}}

=== ISSUE ===
key: CAT-001
title: [ENGINEERING] Catalyst project init: CLI, credits, environments, capability verification report
labels: type:engineering, area:catalyst, priority:p0, risk:catalyst
milestone: M2
estimate: M
risk: HIGH
blocked_by:
--- BODY ---
## Summary
Initialize the real Catalyst project: install `zcatalyst-cli`, claim promotion credits (code KSPH26), create dev environment, commit `catalyst.json`/project config, and produce a **capability verification report** for every service the architecture assumes (Data Store limits, NoSQL, AppSail runtimes, QuickML LLM surface, Signals, Circuits, Cron, SmartBrowz, Push, Auth, API Gateway).

## Problem Statement
The whole architecture (ADR-001/ADR-010) rests on assumed Catalyst capabilities. None are verified: no CLI is installed, no project exists. Any gap discovered late invalidates dependent designs.

## Why This Matters
This is the single highest-leverage de-risking step. MO-002 (QuickML) and EVT-002 (Circuits) explicitly wait on its findings.

## Engineering Objective
Working authenticated CLI + project; `docs/catalyst/capability-report.md` with VERIFIED / UNAVAILABLE / LIMITED per service and concrete limits (row limits, payload sizes, runtimes, region).

## Catalyst Services
All (verification). CLI + console.

## Dependencies
Blocked by: — · Blocks: {{CAT-002}}–{{CAT-006}}, {{MO-002}}, {{EVT-001}}

## Technical Design
`npm i -g zcatalyst-cli` → `catalyst login` → project init in repo root; record project id/zaid in `docs/catalyst/project.md` (no secrets committed); per-service verification with minimal probes (create/drop test table; deploy hello AppSail; list QuickML endpoints; create/delete test signal).

## Security & Privacy
Tokens stay in local CLI config; `.gitignore` covers any credential artifacts; document env-var strategy.

## Edge Cases
Credits not yet claimed (document claim steps + owner action); org/region restrictions; CLI version incompatibilities.

## Acceptance Criteria
- [ ] `catalyst --version` + authenticated `catalyst project:list` documented in report
- [ ] Project config committed (no secrets)
- [ ] Capability report covers all 15+ assumed services with evidence (command output/console screenshot reference)
- [ ] Every UNAVAILABLE/LIMITED capability has a designed fallback documented and linked from the affected issue
- [ ] Credits claim status documented

## Test Plan
Manual verification transcript committed; smoke probes torn down after.

## Definition of Done
Standard DoD; blocked findings escalated in affected issues.

## Demo Evidence
Capability report cited when judges ask "why Catalyst service X?"

## Limitations / Non-Goals
No production tables/functions (CAT-002+).

## References
ADR-001; ADR-010; promotion: catalyst.zoho.com/promotions.html?cn=KSPH26.

=== ISSUE ===
key: CAT-002
title: [ENGINEERING] Catalyst Data Store provisioning matching schema manifest (source + derived tables)
labels: type:engineering, area:catalyst, area:er-schema, priority:p0, risk:catalyst
milestone: M2
estimate: M
risk: MEDIUM
blocked_by: CAT-001, ER-001
--- BODY ---
## Summary
Provision all source FIR tables (exact documented column names) and derived intelligence tables (per derived-intelligence-schema.md) in Catalyst Data Store, with an idempotent provisioning script and a parity check against `schema-manifest.json`.

## Problem Statement
Without physical tables, ingestion (DATA-002) and every engine have nowhere to read/write. Manual console table creation is unreproducible and drift-prone.

## Engineering Objective
`scripts/catalyst/provision_datastore.py` (create-if-missing from manifest) + parity verification command.

## Source Data / ER Schema Mapping
All 26 source tables, columns/keys per matrix §1; column name fidelity is mandatory (incl. `caste_master_id`, `latitude`, `csdate`). Derived tables marked DERIVED per boundary doc.

## ER Conformance Requirements
- Physical column names == documented names (parity check)
- Data Store type mapping documented (DATETIME→datetime, BIT→boolean, NVARCHAR(MAX)→text) — type adaptation is allowed and documented; names/meaning are not
- Referenced-undefined tables NOT created (matrix §2)

## Catalyst Services
Data Store (tables, ZCQL); documented limits from CAT-001 report (max columns/text size) with any constraint noted.

## Dependencies
Blocked by: {{CAT-001}}, {{ER-001}} · Blocks: {{DATA-002}}, {{PROV-001}}, {{EVT-001}}

## Edge Cases
Existing tables with drifted columns (report, never silently alter); Data Store reserved words colliding with column names (documented rename ONLY if forced, with mapping entry + matrix deviation log).

## Acceptance Criteria
- [ ] Provisioning run from clean project creates all tables; second run is a no-op
- [ ] Parity check passes: physical columns == manifest (or documented forced deviations)
- [ ] Type mapping table committed to docs/catalyst/
- [ ] Smoke insert/query via repository against real Data Store succeeds for CaseMaster

## Test Plan
Integration smoke against dev environment; parity unit test.

## Definition of Done
Standard DoD + deviation log empty or justified.

## Demo Evidence
Console/table listing referenced in capability report.

## Limitations / Non-Goals
No data load (DATA-002).

## References
Matrix §1/§5; derived-intelligence-schema.md; ADR-002.

=== ISSUE ===
key: CAT-003
title: [FEATURE] Catalyst Authentication + role/scope model (STATE / DISTRICT / UNIT)
labels: type:feature, area:auth, area:catalyst, priority:p0, area:security
milestone: M2
estimate: M
risk: MEDIUM
blocked_by: CAT-001
--- BODY ---
## Summary
Integrate Catalyst Authentication for login/signup and implement the role model: SCRB_STATE_ANALYST, DISTRICT_ANALYST, SUPERVISOR, INVESTIGATOR, SYSTEM_ADMIN with scope claims (STATE | DISTRICT(id) | UNIT(id)) resolved server-side.

## Problem Statement
All intelligence data is sensitive; there is no auth. Scope enforcement (SEC-001) needs a trustworthy identity + role source, which must be Catalyst Authentication per the mandate.

## User Story
As an SCRB administrator, I want role-scoped user accounts, so that a district analyst can never read another district's raw intelligence.

## Source Data / ER Schema Mapping
Role scope references District.DistrictID and Unit.UnitID (OBSERVED lookups); user↔role mapping is a DERIVED app table (`UserRoleAssignment`: user_id, role, scope_type, scope_id).

## Catalyst Services
Authentication (login, session/JWT validation); Data Store (UserRoleAssignment).

## Dependencies
Blocked by: {{CAT-001}} · Blocks: {{SEC-001}}, {{UI-001}}, {{CAT-004}}, {{ENT-003}}, {{PROV-003}}

## Technical Design
Backend middleware validates Catalyst auth token per request → loads role assignment → attaches `AuthContext{user_id, role, scope}` consumed by repositories/APIs. Deny-by-default: no assignment → 403.

## Security & Privacy
No client-supplied scope honored; role changes audited (PROV-003); test users documented for demo.

## Edge Cases
User with multiple roles (highest-privilege wins? No — explicit priority documented); deleted scope target; expired token.

## Acceptance Criteria
- [ ] Login via Catalyst Auth works in deployed dev environment
- [ ] Request without valid token → 401; without role assignment → 403
- [ ] AuthContext exposes role+scope to handlers (unit-tested with mocked validator)
- [ ] Demo users for each role seeded and documented

## Test Plan
Unit: middleware with forged/expired tokens. Integration: real login flow. Security: token tamper test.

## Definition of Done
Standard DoD + demo credentials documented (non-secret env).

## Demo Evidence
Login screen → role-appropriate landing.

## Limitations / Non-Goals
Fine-grained per-record ACLs; SSO federation.

## References
ADR-001; {{SEC-001}}.

=== ISSUE ===
key: CAT-004
title: [ENGINEERING] Catalyst API Gateway routing, throttling and auth in front of backend
labels: type:engineering, area:catalyst, area:security, priority:p1
milestone: M2
estimate: S
risk: LOW
blocked_by: CAT-003, CAT-005
--- BODY ---
## Summary
Front all backend routes with Catalyst API Gateway: route definitions, auth requirement per route group, basic throttling, and consistent error envelope.

## Problem Statement
Direct AppSail exposure bypasses the mandated gateway capability and loses central throttling/auth enforcement.

## Engineering Objective
Gateway config in repo; all frontend calls go through gateway URLs.

## Catalyst Services
API Gateway; Authentication (integration); AppSail (target).

## Dependencies
Blocked by: {{CAT-003}}, {{CAT-005}} · Blocks: {{DEMO-005}}

## Acceptance Criteria
- [ ] All /api/* routes resolve through the gateway in the deployed environment
- [ ] Unauthenticated request to protected route rejected at gateway
- [ ] Throttle rule configured + documented
- [ ] Config committed/reproducible

## Test Plan
Integration curl matrix (auth/no-auth per route group).

## Definition of Done
Standard DoD.

## Demo Evidence
Network tab shows gateway origin.

## Limitations / Non-Goals
Per-user rate tiers.

## References
ADR-001.

=== ISSUE ===
key: CAT-005
title: [ENGINEERING] AppSail analytics runtime deployment (Python/FastAPI)
labels: type:engineering, area:catalyst, priority:p0, risk:catalyst
milestone: M2
estimate: M
risk: MEDIUM
blocked_by: CAT-001, GOV-001
--- BODY ---
## Summary
Deploy the backend (FastAPI + scientific stack) to Catalyst AppSail; establish config/env handling, deploy script, health/readiness endpoints, and verify scientific dependencies (numpy/scikit-learn/networkx) run within AppSail limits.

## Problem Statement
ADR-010 assumes AppSail can host the Python analytics runtime with its dependency weight; unverified. Engines have no execution home until this works.

## Engineering Objective
`make deploy-backend` → live AppSail URL serving `/health` with dependency check.

## Catalyst Services
AppSail (managed Python runtime or custom OCI if needed — decide from CAT-001 findings and document).

## Dependencies
Blocked by: {{CAT-001}}, {{GOV-001}} · Blocks: {{CAT-004}}, {{CAT-006}}, {{HOT-003}}, {{EVT-003}}, {{DEMO-003}}

## Technical Design
App config (port/env per AppSail contract); Data Store SDK wiring via env; startup import-check endpoint `/health/deps` returning versions of numpy/sklearn/networkx/pandas.

## Edge Cases
Build size limits (prune deps; wheels); cold start; memory ceiling under clustering load (document limit; scope windows accordingly).

## Acceptance Criteria
- [ ] Deployed URL serves /health and /health/deps with all scientific libs importable
- [ ] Deploy script reproducible from clean checkout (documented prerequisites)
- [ ] Env/config strategy documented; no secrets in repo
- [ ] A sample scoped Data Store query executes from deployed runtime

## Test Plan
Manual deploy + smoke; load one clustering call on sample data to observe memory/time.

## Definition of Done
Standard DoD + limits recorded in capability report.

## Demo Evidence
Deployed health endpoints.

## Limitations / Non-Goals
Autoscaling tuning.

## References
ADR-010; {{CAT-001}}.

=== ISSUE ===
key: CAT-006
title: [ENGINEERING] Frontend hosting via Catalyst Web Client Hosting
labels: type:engineering, area:catalyst, area:frontend, priority:p0
milestone: M2
estimate: S
risk: LOW
blocked_by: CAT-001, UI-001
--- BODY ---
## Summary
Host the built React SPA on Catalyst Web Client Hosting with environment-aware API base URL (gateway), SPA fallback routing, and a deploy script.

## Problem Statement
The mandated frontend hosting is Catalyst (Slate or Web Client Hosting); local dev serving is not a submission.

## Catalyst Services
Web Client Hosting; API Gateway (base URL).

## Dependencies
Blocked by: {{CAT-001}}, {{UI-001}} · Blocks: {{DEMO-003}}, {{DEMO-005}}

## Acceptance Criteria
- [ ] `make deploy-frontend` publishes the built SPA to the Catalyst-hosted URL
- [ ] Deep links (e.g. /geo/district/44) load via SPA fallback
- [ ] API calls hit gateway URL from hosted origin (CORS verified)
- [ ] Login flow works end-to-end on hosted URL

## Test Plan
Manual hosted smoke across major routes.

## Definition of Done
Standard DoD.

## Demo Evidence
The judge-facing URL.

## Limitations / Non-Goals
Custom domain (optional Domain Mappings, P3).

## References
ADR-001.
