# KAVACH AI — Target Architecture

**Product:** KAVACH AI — Karnataka Crime Intelligence & Analytical Platform
**Mission:** From Fragmented FIR Records to Connected, Explainable and Proactive Crime Intelligence.
**Challenge:** Challenge 2 — AI-Driven Crime Analytics & Visualization Platform (locked).
**Deployment:** Catalyst by Zoho (mandatory) — see ADR-001.

## Logical architecture

```
                         KSP / SCRB USER
                                │
                    CATALYST AUTHENTICATION (ADR-001)
                                │
                       CATALYST API GATEWAY
                                │
              ┌─────────────────┴─────────────────┐
              │        KAVACH AI WEB (React SPA)  │
              │  Catalyst Web Client Hosting      │
              └─────────────────┬─────────────────┘
                                │ REST (scope-enforced server-side)
              ┌─────────────────┴─────────────────┐
              │   ANALYTICS RUNTIME (Python)      │
              │   Catalyst AppSail (ADR-010)      │
              │  ┌──────────┬──────────┬────────┐ │
              │  │ Hotspot/ │ Graph &  │ MO/AI  │ │
              │  │ Trend    │ Identity │ engine │─┼── Catalyst QuickML (LLM)
              │  │ engines  │ engines  │        │ │
              │  └──────────┴──────────┴────────┘ │
              └─────────────────┬─────────────────┘
                                │
                     CATALYST DATA STORE  ── source FIR tables (exact ER schema)
                     CATALYST NoSQL       ── MO profiles (AI_DERIVED)
                     CATALYST STRATUS     ── generated reports/exports
                                │
                     CATALYST SIGNALS → EVENT FUNCTION → CIRCUITS
                     (new-FIR event → parallel: MO extraction | hotspot update |
                      entity candidates | anomaly features → risk/trend update →
                      threshold evaluation → alert → Push Notification)
                     CATALYST CRON        ── scheduled recalculation
```

## Layering
1. **Source layer** — FIR tables exactly as documented ([er-conformance-matrix.md](../schema/er-conformance-matrix.md)). Read-only for analytics.
2. **Provenance layer** — IntelligenceRun/IntelligenceEvidence ([derived-intelligence-schema.md](../schema/derived-intelligence-schema.md)). Every engine writes through it.
3. **Engine layer** — hotspot, trend, MO, graph, entity resolution, anomaly, area risk. Deterministic where possible (ADR-008), explainable always.
4. **API layer** — Catalyst Functions/AppSail routes behind API Gateway; server-side district/unit scoping (ADR-001, SEC-001).
5. **Experience layer** — intelligence-story UI: Overview → Geospatial → Trends → Networks → MO → Identity Review → Anomaly → Risk → Evidence.

## Security boundaries
- AuthN: Catalyst Authentication. AuthZ scopes: STATE / DISTRICT / UNIT resolved server-side from role assignment; client filters are cosmetic only.
- PII minimization: victim/complainant names never in state-level aggregates; protected demographics (caste/religion) never used as offender or area profiling features (ADR-009).
- Audit: identity review decisions, sensitive case access, report generation.

## Analytics lifecycle
INGEST → VALIDATE → FEATURE → ANALYZE → EVIDENCE → PERSIST → API → UI → HUMAN REVIEW → FEEDBACK (learning loop, ADR-004).

## ADR index
| ADR | Decision |
|---|---|
| [ADR-001](adr/ADR-001-catalyst-native-architecture.md) | Catalyst-native architecture |
| [ADR-002](adr/ADR-002-data-store-primary-persistence.md) | Data Store as primary relational persistence |
| [ADR-003](adr/ADR-003-personid-not-global-identity.md) | Accused.PersonID is not a global identity |
| [ADR-004](adr/ADR-004-human-in-the-loop-entity-resolution.md) | Human-in-the-loop entity resolution |
| [ADR-005](adr/ADR-005-area-level-risk-only.md) | Area-level risk, no individual predictive policing |
| [ADR-006](adr/ADR-006-structured-mo-extraction.md) | Structured MO schema for BriefFacts AI enrichment |
| [ADR-007](adr/ADR-007-evidence-backed-graph.md) | Evidence-backed derived graph |
| [ADR-008](adr/ADR-008-statistical-methods-first.md) | Statistical methods before deep learning |
| [ADR-009](adr/ADR-009-data-classification-and-demographics.md) | Observed/AI-derived/human-confirmed classification; complainant demographics boundary |
| [ADR-010](adr/ADR-010-appsail-vs-functions-boundary.md) | AppSail vs Functions boundary |
| [ADR-011](adr/ADR-011-demo-data-strategy.md) | Demo data strategy |
