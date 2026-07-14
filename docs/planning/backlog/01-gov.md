=== ISSUE ===
key: EPIC-GOV
title: [EPIC] Repository Governance & Architecture Control
labels: type:epic, priority:p0
milestone: M0
estimate: -
risk: LOW
blocked_by:
--- BODY ---
## Problem
The repository must carry the engineering story: governed structure, recorded decisions, CI. Without this, every later issue lacks a home and judges cannot audit decisions.

## Why it matters
Judges reading Issues/commits before the demo must see production-minded delivery. All other epics depend on the scaffolding.

## Challenge requirement
Foundational (all of C2-R1…R12).

## Technical scope
Monorepo scaffolding (backend AppSail Python, Catalyst functions, frontend SPA, docs), ADR set, CI checks.

## Out of scope
Any analytics or Catalyst provisioning (EPIC-CAT).

## Source data
None.

## Catalyst services
None directly; structure anticipates AppSail/Functions/Web Client layout (ADR-010).

## Deliverables & success criteria
- {{GOV-001}} scaffolding merged, lint/test runnable
- {{GOV-002}} ADR-001…011 + target architecture committed
- {{GOV-003}} CI runs lint+tests on PRs

## Risks
Low.

## Demo impact
Indirect — enables everything.

## Child issues
- {{GOV-001}}, {{GOV-002}}, {{GOV-003}}

=== ISSUE ===
key: GOV-001
title: [ENGINEERING] Monorepo scaffolding: backend (AppSail/Python), functions, frontend, docs
labels: type:engineering, priority:p0, area:catalyst
milestone: M0
estimate: M
risk: LOW
blocked_by:
--- BODY ---
## Summary
Create the governed monorepo structure that every subsequent issue implements into: a Python FastAPI analytics service targeting Catalyst AppSail, a `functions/` directory for Catalyst Serverless/Event functions, a React SPA for Catalyst Web Client Hosting, shared docs, and tooling config.

## Problem Statement
The repository contains only a README. There is no module structure, dependency manifest, lint/test tooling, or agreed layout, so no engine, mapping, or UI issue can start without inventing structure ad hoc.

## Why This Matters
Every epic (ER, DATA, CAT, analytics, UI) lands code here; a wrong or absent structure creates rework across ~60 issues. The AppSail/Functions boundary (ADR-010) must be visible in the tree.

## Engineering Objective
Deliver the skeleton with zero business logic and passing quality gates.

## Source Data / ER Schema Mapping
None (structure only). No source table may be modelled in this issue.

## Catalyst Services
Structure anticipates: AppSail (backend/), Serverless Functions (functions/), Web Client Hosting (frontend/). No provisioning here ({{CAT-001}}).

## Dependencies
Blocked by: — · Blocks: {{ER-002}}, {{CAT-005}}, {{UI-001}}, {{GOV-003}}

## Technical Design
```
backend/            # Python 3.12, FastAPI, targets AppSail
  kavach/
    domain/         # ER-mapped entities (ER-002..006)
    repositories/   # Data Store access (+ local SQLite dev fixture)
    analytics/      # engines (hotspot/, trends/, mo/, graph/, entity/, anomaly/, risk/)
    provenance/     # IntelligenceRun/Evidence (PROV-001)
    api/            # FastAPI routers
    config.py
  tests/
  pyproject.toml    # ruff + pytest
functions/          # Catalyst event/cron functions (Node or Python per CAT-001 findings)
frontend/           # Vite + React + TypeScript
  src/{app,features,components,lib}
docs/               # already present
scripts/
catalyst.json       # placeholder until CAT-001
```
Local dev: `uv`/pip + venv; frontend `npm`. Makefile targets: `make lint test build`.

## Edge Cases
Node/Python version pinning (`.python-version`, `engines`); Windows-safe paths not required (team on Linux).

## Acceptance Criteria
- [ ] `cd backend && ruff check . && pytest` passes (with a placeholder health test)
- [ ] `cd frontend && npm run build` succeeds
- [ ] `GET /health` returns `{status:"ok"}` when running `uvicorn kavach.api.main:app`
- [ ] Directory layout matches ADR-010 boundary; README updated with structure map
- [ ] No business logic, no fake analytics, no invented ER models

## Test Plan
Unit: health endpoint test. Manual: run backend + frontend dev servers.

## Definition of Done
Implementation + criteria above + CI-compatible commands documented + commit references issue.

## Demo Evidence
`make lint test` output; repo tree in README.

## Limitations / Non-Goals
No Catalyst deployment, no auth, no data models.

## References
ADR-010; delivery-plan.md.

=== ISSUE ===
key: GOV-002
title: [DOCS] Architecture decision records + target architecture baseline
labels: type:docs, priority:p0
milestone: M0
estimate: S
risk: LOW
blocked_by:
--- BODY ---
## Summary
Commit the architecture control baseline: ADR-001…ADR-011, target-architecture.md, ER conformance matrix, derived-intelligence schema boundary, challenge traceability YAML, delivery plan.

## Problem Statement
Without recorded decisions, later contributors (and judges) cannot distinguish deliberate constraints (e.g., PersonID semantics, Catalyst-native rule) from accidents.

## Engineering Objective
All architecture-control documents exist in `docs/`, are internally consistent, and are referenced from the README.

## Source Data / ER Schema Mapping
References the full ER catalogue (docs/schema/er-conformance-matrix.md); no code mapping.

## Catalyst Services
Documented in ADR-001/ADR-010.

## Dependencies
Blocked by: — · Blocks: all epics (reference baseline)

## Acceptance Criteria
- [ ] ADR-001…011 present with Status/Context/Decision/Alternatives/Consequences/Risks/Revisit
- [ ] er-conformance-matrix.md catalogues 26 defined tables + 2 referenced-undefined tables + quirks Q1–Q10
- [ ] challenge-traceability.yaml maps all 12 requirements to issues
- [ ] README links every document

## Definition of Done
Docs merged to main; issue closed with commit SHA.

## Demo Evidence
Repo docs/ tree; judges can read decisions before demo.

## Limitations / Non-Goals
Docs only.

## References
docs/architecture/, docs/schema/, docs/traceability/.

=== ISSUE ===
key: GOV-003
title: [ENGINEERING] CI checks: lint + tests on every push/PR (GitHub Actions until Catalyst Pipelines)
labels: type:engineering, priority:p1, area:catalyst
milestone: M0
estimate: S
risk: LOW
blocked_by: GOV-001
--- BODY ---
## Summary
Add GitHub Actions workflow running backend ruff+pytest and frontend typecheck+build on push/PR. Catalyst Pipelines takes over deployment CI in {{DEMO-005}}; this issue covers quality gates during development.

## Problem Statement
Without CI, conformance tests (ER-007) and analytics validation suites cannot gate merges, and "tests pass" claims are unverifiable.

## Engineering Objective
Red/green signal on every push; required for Definition of Done across the backlog.

## Catalyst Services
None (development CI). Catalyst Pipelines documented as the deployment pipeline (ADR-001), integrated in {{DEMO-005}}.

## Dependencies
Blocked by: {{GOV-001}} · Blocks: {{ER-007}} usefulness

## Acceptance Criteria
- [ ] Workflow runs `ruff check`, `pytest`, `npm run build` (frontend), `tsc --noEmit`
- [ ] Fails on lint/test failure; badge in README
- [ ] Runtime < 5 min with dependency caching

## Definition of Done
Green run on main; badge visible.

## Limitations / Non-Goals
No deployment from Actions — deployment stays Catalyst-native.

## References
{{GOV-001}}; ADR-001.
