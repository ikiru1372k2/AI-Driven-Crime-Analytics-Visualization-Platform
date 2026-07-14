# KAVACH AI — Engineering Delivery Plan

Backlog source of truth: issue bodies in [docs/planning/backlog/](backlog/), created on GitHub by `scripts/github/create_backlog.py`. Key→issue-number map: [issue-map.json](issue-map.json).

## Milestones

| # | Milestone | Objective | Exit criteria | Demo unlocked |
|---|---|---|---|---|
| M0 | Repository & Architecture Control | Governed monorepo, ADRs, CI | Scaffolding merged; ADRs committed; CI green | — |
| M1 | FIR Data Foundation & ER Conformance | Exact ER schema in code + validated synthetic dataset | Conformance tests pass; dataset generated & ingested locally | — |
| M2 | Catalyst Platform Foundation | Catalyst project live: Data Store, Auth, AppSail, hosting | Tables provisioned; auth roles work; AppSail serves API | Login + empty shell |
| M3 | Analytics Foundation & Provenance | IntelligenceRun/Evidence framework + audit | Every engine can persist evidence with method version | Evidence drawer (skeleton) |
| M4 | Spatiotemporal Intelligence | Hotspot + trend engines with validation | Known synthetic cluster & spike detected; no-alert stability test passes | D1, D2 |
| M5 | MO Intelligence | QuickML MO extraction + similarity | Schema-valid extraction with UNKNOWN handling; similarity ranked | D3 |
| M6 | Association & Identity Intelligence | Graph + human-in-loop entity resolution | Evidence-backed edges; candidate→review→confirm flow audited | D4, D5 |
| M7 | Anomaly & Area Risk Intelligence | Explained anomaly + validated area risk | Factor explanations; temporal holdout, no future leakage | D6, D7 |
| M8 | Intelligence Visualization Experience | Full intelligence-story UI | All screens live vs real APIs; classification labels visible | D1–D8 |
| M9 | Event-Driven Automation, Security & Governance | Signals/Circuits pipeline + scope enforcement | New-FIR event triggers analytics; scope bypass tests pass | D9 |
| M10 | Demo, Deployment & Submission | Deterministic demo, deployed, submission-ready | Reset script; 5-min route rehearsed; deployment URL verified | Full demo |

## Epics → milestones

| Epic | Title | Milestone |
|---|---|---|
| EPIC-GOV | Repository Governance & Architecture Control | M0 |
| EPIC-ER | FIR ER Schema Conformance | M1 |
| EPIC-DATA | Crime Data Ingestion & Demo Dataset | M1 |
| EPIC-CAT | Catalyst Platform Foundation | M2 |
| EPIC-PROV | Intelligence Evidence & Provenance | M3 |
| EPIC-HOT | Spatiotemporal Hotspot Analytics | M4 |
| EPIC-TREND | Emerging Trend Detection | M4 |
| EPIC-MO | AI MO Extraction & Similarity | M5 |
| EPIC-GRAPH | Crime Association Graph | M6 |
| EPIC-ENT | Cross-FIR Entity Resolution | M6 |
| EPIC-ANOM | Behavioral Anomaly Detection | M7 |
| EPIC-RISK | Area Risk Intelligence | M7 |
| EPIC-UI | State Intelligence Experience | M8 |
| EPIC-EVT | Catalyst Event Orchestration | M9 |
| EPIC-SEC | Security, Scope Enforcement & Governance | M9 |
| EPIC-DEMO | Competition Demo Reliability & Submission | M10 |

## Dependency graph (critical path in bold)

```
GOV-001 ─┬─▶ ER-002..ER-006 ─▶ ER-007
         │        │
CAT-001 ─┼─▶ CAT-002 ─▶ DATA-002 ◀─ DATA-001 ◀─ ER-001
         │        │         │
         │   CAT-003    PROV-001 ─▶ PROV-002
         │      │            │
         │   SEC-001     ┌───┴────────┬──────────┬─────────┐
         │               ▼            ▼          ▼         ▼
         │          **HOT-001**   TREND-001   MO-001    GRAPH-001
         │               ▼            ▼          ▼         ▼
         │          **HOT-002**   TREND-002   MO-002    GRAPH-002
         │               ▼            ▼          ▼         ▼
         │          **HOT-003**   TREND-003   MO-003    GRAPH-003
         │               │            │       MO-004
         │               │            │          │      ENT-001 ─▶ ENT-002 ─▶ ENT-003 ─▶ ENT-004
         │               │            │          │
         │               │        RISK-001 ◀────┘ (velocity+clusters+MO recurrence)
         │               │            ▼
         │               │        RISK-002 ─▶ RISK-003        ANOM-001 ─▶ ANOM-002 ─▶ ANOM-003
         ▼               ▼
      UI-001 ──▶ **UI-002** / UI-003 / UI-005..UI-009 ─▶ UI-010
                         │
      EVT-001 ─▶ EVT-002 ─▶ EVT-003 / EVT-004
                         │
      DEMO-001 ─▶ **DEMO-002** ─▶ DEMO-003 ─▶ DEMO-005 ; DEMO-004
```

**Critical path:** GOV-001 → CAT-001 → CAT-002 → ER-002 → DATA-001 → DATA-002 → PROV-001 → HOT-001 → HOT-002 → HOT-003 → UI-001 → UI-002 → DEMO-001 → DEMO-002 → DEMO-005.

**Parallel workstreams after DATA-002 + PROV-001:** (a) hotspot/trend, (b) MO/QuickML, (c) graph/entity-resolution, (d) UI foundation, (e) Catalyst events.

## Master Delivery Index

- Milestones: 11 (M0–M10) · Epics: 16 · Executable issues: 68 · Total GitHub issues: 84 (#1–#84, see issue-map.json)
- Priority (executable): P0 = 48 · P1 = 19 · P2 = 1
- Highest-risk issues: MO-002 (QuickML capability), CAT-002 (Data Store limits), RISK-002 (validation honesty), EVT-002 (Circuits availability), DEMO-005 (deployment)
- Catalyst-dependent: all CAT-*, MO-002, EVT-*, DEMO-003, DEMO-005
- ER conformance issues: ER-001…ER-007 · ML validation: HOT-004, TREND-003, MO-005, ENT-004, ANOM-003, RISK-003 · Security: CAT-003, CAT-004, SEC-001..003, PROV-003 · Demo-critical: DEMO-001..005, UI-002, UI-003, UI-009
- Challenge coverage: 12/12 requirements traced (see challenge-traceability.yaml); C2-R8 (socio-economic overlay) is EXTERNAL_DATA_REQUIRED — shipped as documented integration point unless genuine public data is added
- Dataset limitation: no real FIR data supplied → deterministic synthetic dataset (ADR-011), all outputs labelled
- Submission risks: QuickML feature surface unverified until CAT-001; Circuits/Signals availability unverified until M2; Catalyst credits must be claimed (KSPH26)

### P0 execution order (first 15)

| # | Issue | Blocked by | Output |
|---|---|---|---|
| 1 | ER-001 | — | Authoritative conformance matrix |
| 2 | GOV-001 | — | Monorepo scaffolding |
| 3 | GOV-002 | — | ADRs + architecture docs committed |
| 4 | CAT-001 | — | Catalyst project + CLI + env |
| 5 | ER-002 | GOV-001, ER-001 | CaseMaster + case-linked mappings |
| 6 | ER-003 | GOV-001, ER-001 | Person-record mappings + guards |
| 7 | ER-004 | GOV-001, ER-001 | Legal/classification lookups |
| 8 | ER-005 | GOV-001, ER-001 | Geography/org hierarchy |
| 9 | ER-006 | ER-002, ER-003 | ArrestSurrender mapping |
| 10 | CAT-002 | CAT-001, ER-001 | Data Store tables |
| 11 | DATA-001 | ER-001 | Synthetic dataset generator |
| 12 | ER-007 | ER-002..006 | Conformance test suite |
| 13 | DATA-002 | DATA-001, CAT-002, ER-002..006 | Ingestion + validation |
| 14 | CAT-003 | CAT-001 | Auth + roles |
| 15 | PROV-001 | ER-002, CAT-002 | Evidence framework |
