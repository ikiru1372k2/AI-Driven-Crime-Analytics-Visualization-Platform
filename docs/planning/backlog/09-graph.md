=== ISSUE ===
key: EPIC-GRAPH
title: [EPIC] Crime Association Graph
labels: type:epic, area:graph, area:analytics, priority:p0
milestone: M6
estimate: -
risk: MEDIUM
blocked_by:
--- BODY ---
## Problem
Fragmented FIR records hide cross-case structure: co-accused patterns, shared locations, recurring classifications. No relationship projection exists; the challenge explicitly demands network & link analysis that replaces "independent silos".

## Why it matters
C2-R5 (relationship mapping, association detection); provides co-accused overlap signals to entity resolution; demo step D4.

## Challenge requirement
C2-R5; supports C2-R6.

## Technical scope
Deterministic relational→graph projection with edge provenance, graph metrics with careful interpretation, scoped API.

## Out of scope
Graph DB (rejected, ADR-007); identity merging ({{EPIC-ENT}}); UI ({{UI-005}}).

## Source data
Accused, Victim (aggregate), CaseMaster, Unit, District, CrimeHead/SubHead, Court, ArrestSurrender — all OBSERVED; SIMILAR_MO edges from {{MO-004}} (POTENTIAL_ASSOCIATION).

## Catalyst services
Data Store, AppSail (NetworkX).

## Deliverables & success criteria
Every edge has evidence_case_id + derivation; ground-truth co-accused chains recovered; metrics reproducible.

## Risks
Interpretation drift ("gang leader") — wording constraints enforced in UI copy + API labels.

## Demo impact
D4 — association graph navigation.

## Child issues
{{GRAPH-001}}, {{GRAPH-002}}, {{GRAPH-003}}

=== ISSUE ===
key: GRAPH-001
title: [FEATURE] Deterministic graph projection: nodes/edges from relational records with mandatory provenance
labels: type:feature, area:graph, priority:p0
milestone: M6
estimate: M
risk: LOW
blocked_by: DATA-002, ER-003, PROV-001
--- BODY ---
## Summary
Project relational records into CrimeGraphNode/CrimeGraphEdge tables: node types (CASE, ACCUSED_RECORD, VICTIM_RECORD, POLICE_STATION, DISTRICT, CRIME_HEAD, CRIME_SUBHEAD, COURT), observed edges (ACCUSED_IN, VICTIM_IN, REGISTERED_AT, OCCURRED_IN, CLASSIFIED_AS, LINKED_TO_SECTION, ARRESTED_IN, PRODUCED_AT) and derived edges (SHARES_CASE_WITH between accused records co-occurring in a case; SIMILAR_MO from {{MO-004}}) — every edge carrying evidence_case_id + derivation + classification.

## Problem Statement
Relationship data exists only as FK columns; analysts cannot see cross-case structure, and ad-hoc joins have no provenance or reproducibility.

## Why This Matters
C2-R5 core; co-accused projection is the entity-resolution overlap signal (ENT-002); D4 demo.

## Source Data / ER Schema Mapping (OBSERVED unless noted)
```
Accused.AccusedMasterID + CaseMasterID → ACCUSED_RECORD node + ACCUSED_IN edge (node identity = AccusedMasterID — NEVER PersonID, ADR-003)
Victim → VICTIM_RECORD node + VICTIM_IN (aggregate-safe labels, no names in node label at state scope)
CaseMaster.PoliceStationID → REGISTERED_AT; Unit→District → OCCURRED_IN context
CaseMaster.CrimeMajorHeadID/CrimeMinorHeadID → CLASSIFIED_AS
ActSectionAssociation → LINKED_TO_SECTION
ArrestSurrender → ARRESTED_IN (unit), PRODUCED_AT (court)
Derived: (a,b) accused in same case → SHARES_CASE_WITH {evidence_case_id, derivation: CASE_CO_OCCURRENCE, classification: DERIVED_METRIC}
Derived: MO-004 similar pairs → SIMILAR_MO {classification: POTENTIAL_ASSOCIATION}
```

## ER Conformance Requirements
- Node identity for accused = AccusedMasterID (guard test — no PersonID keying)
- No edge without evidence_case_id (DB not-null + tests)
- Projection is idempotent + reproducible per run_id

## Catalyst Services
Data Store (graph tables), AppSail.

## Dependencies
Blocked by: {{DATA-002}}, {{ER-003}}, {{PROV-001}} · Blocks: {{GRAPH-002}}, {{ENT-002}}, {{UI-005}}

## Edge Cases
Case with 1 accused (no SHARES_CASE_WITH); duplicate projection runs (replace-by-run semantics); dangling FKs (skip + count); very large cases (50 accused → C(50,2) edges — cap with documented aggregation).

## Acceptance Criteria
- [ ] Ground-truth co-accused chain (DATA-001) fully present with correct evidence_case_ids
- [ ] Attempted edge insert without evidence_case_id fails (test)
- [ ] Re-projection on unchanged data yields identical node/edge sets
- [ ] PersonID guard test passes (no identity keyed on PersonID)

## Test Plan
Unit: projection rules per edge type. Integration: full synthetic projection; determinism check.

## Definition of Done
Standard DoD + ER gate.

## Demo Evidence
D4 graph rendering; edge click shows evidence case.

## Limitations / Non-Goals
Metrics (GRAPH-002); no cross-case identity edges (that's ENT candidates, rendered distinctly).

## References
ADR-003; ADR-007; derived-intelligence-schema.md.

=== ISSUE ===
key: GRAPH-002
title: [FEATURE] Graph metrics: components, centrality, communities, co-occurrence — with interpretation constraints
labels: type:feature, area:graph, area:ml, priority:p1
milestone: M6
estimate: M
risk: MEDIUM
blocked_by: GRAPH-001
--- BODY ---
## Summary
Compute per-projection metrics on the accused co-occurrence subgraph: connected components, degree centrality, betweenness (per component, size-capped), community detection (Louvain/label propagation), co-occurrence frequency, Jaccard common-neighbor similarity — persisted with method version and rendered with constrained interpretation labels.

## Problem Statement
A rendered graph without metrics can't answer "which records bridge clusters?"; but naive metric labels ("mastermind") would fabricate criminological claims.

## Algorithm / Analytical Method
NetworkX: components; degree; betweenness exact for components ≤ 2000 nodes else sampled k=min(500,n) (documented); Louvain communities (seeded, deterministic); metrics recomputed per projection run. Interpretation mapping is fixed vocabulary: high betweenness → "high-connectivity bridge in the observed case-association graph"; high degree → "frequently co-occurring accused record". PROHIBITED terms in API/UI copy: gang leader, mastermind, kingpin (lint test on copy strings).

## Source Data / ER Schema Mapping
CrimeGraphNode/Edge (DERIVED). Metrics = DERIVED_METRIC / STATISTICAL_INFERENCE.

## Dependencies
Blocked by: {{GRAPH-001}} · Blocks: {{GRAPH-003}}, {{ENT-002}} (graph-overlap feature)

## Edge Cases
Singleton components; complete-graph mega-case artifacts (flag as case-size artifact, exclude from bridge ranking with documented rule); deterministic community seeds.

## Acceptance Criteria
- [ ] Ground-truth bridge record (DATA-001 identity-fragment individual co-occurring across clusters) ranks top-3 betweenness in its component
- [ ] Metrics reproducible across runs (fixed seeds)
- [ ] Interpretation vocabulary test: prohibited terms absent
- [ ] Metric rows carry method version + run_id

## Test Plan
Unit vs hand-computed toy graphs; validation vs ground truth; determinism.

## Definition of Done
Standard DoD.

## Demo Evidence
Node panel: "connected to 3 observed case clusters" with metric basis.

## Limitations / Non-Goals
Metrics describe the observed record graph, not real-world social structure (limitation string shipped with every response).

## References
ADR-007.

=== ISSUE ===
key: GRAPH-003
title: [FEATURE] Graph API: scoped subgraph retrieval, node detail, expansion
labels: type:feature, area:graph, priority:p1
milestone: M6
estimate: S
risk: LOW
blocked_by: GRAPH-002, CAT-003
--- BODY ---
## Summary
REST endpoints for graph exploration: subgraph by seed node with depth limit, node detail (metrics + evidence), expansion pagination — scope-enforced and classification-enveloped.

## API Contract
- `GET /api/v1/graph/subgraph?seed_type=&seed_id=&depth<=2&limit=` (scope-filtered: district analyst sees only cases in scope; cross-scope edges stubbed with count, not detail)
- `GET /api/v1/graph/nodes/{node_id}` → metrics, linked cases (evidence), interpretation label
- Envelope: every edge carries relationship_type, derivation, evidence_case_id, classification

## Dependencies
Blocked by: {{GRAPH-002}}, {{CAT-003}} · Blocks: {{UI-005}}

## Edge Cases
Depth explosion (hard cap + "N more" stubs); seed not found; scope-boundary edges.

## Acceptance Criteria
- [ ] Depth-2 subgraph for ground-truth accused returns expected nodes/edges (fixture)
- [ ] Cross-scope leakage test: district analyst cannot retrieve other-district node details
- [ ] p95 < 800ms on synthetic dataset
- [ ] Contract tests + OpenAPI

## Definition of Done
Standard DoD.

## Demo Evidence
Feeds D4 interactive graph.

## Limitations / Non-Goals
Layout is client-side (UI-005).

## References
{{SEC-001}}; {{PROV-002}}.
