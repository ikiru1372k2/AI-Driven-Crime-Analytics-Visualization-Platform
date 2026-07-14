# Derived Intelligence Schema Boundary

**Status:** DESIGN — implemented by PROV-001/MO-003/ENT-003.
All tables here are **DERIVED** — they are produced by KAVACH analytics, never part of the source FIR ER schema, and are always distinguishable from source records.

Every derived record carries a mandatory classification:

| Class | Meaning | Examples |
|---|---|---|
| `FACT` | Direct restatement of a source column | case count per station |
| `DERIVED_METRIC` | Deterministic computation from FACTs | weekly baseline, cluster density |
| `STATISTICAL_INFERENCE` | Statistical result with uncertainty | trend z-score, anomaly score |
| `AI_DERIVED` | LLM/ML-produced attribute with confidence | MO attributes, match scores |
| `POTENTIAL_ASSOCIATION` | Suggested, unconfirmed relationship | identity candidate, MO similarity edge |
| `HUMAN_CONFIRMED` | Reviewed and confirmed by an authorized user | confirmed identity match |

## Derived tables (Catalyst Data Store unless noted)

### IntelligenceRun
`run_id (PK)`, `intelligence_type` (HOTSPOT | TREND_ALERT | MO_PROFILE | MO_SIMILARITY | ASSOCIATION | IDENTITY_CANDIDATE | ANOMALY | AREA_RISK), `method_name`, `method_version`, `model_version?`, `analysis_window_from`, `analysis_window_to`, `scope_district_id?`, `scope_unit_id?`, `status` (RUNNING | COMPLETED | FAILED), `error?`, `generated_at`, `record_count`.

### IntelligenceEvidence
`evidence_id (PK)`, `run_id (FK IntelligenceRun)`, `result_ref` (id of hotspot/alert/candidate…), `evidence_case_ids` (JSON array of CaseMaster.CaseMasterID), `factors` (JSON: name → contribution), `limitations` (JSON array), `classification` (enum above).

### HotspotResult / TrendAlert / AnomalyResult / AreaRiskScore
Engine result tables; every row references `run_id` and is reproducible from source rows + method version. Fields specified in each engine's issue.

### MoProfile (Catalyst NoSQL)
`case_master_id`, extracted attribute set per MO-001 schema, per-attribute `{value, confidence, source_span?}`, `model_version`, `extracted_at`. Classification: `AI_DERIVED`. Unknown values stored as `"UNKNOWN"` — never invented.

### CrimeGraphNode / CrimeGraphEdge
Node: `node_id (PK)`, `node_type` (CASE | ACCUSED_RECORD | VICTIM_RECORD | POLICE_STATION | DISTRICT | CRIME_HEAD | CRIME_SUBHEAD | COURT), `entity_ref_id`, `label`.
Edge: `edge_id (PK)`, `source_node_id`, `target_node_id`, `relationship_type`, `weight`, `evidence_case_id` (mandatory — no unexplained edges), `derivation`, `classification`.

### EntityResolutionCandidate
`candidate_id (PK)`, `accused_record_a` (Accused.AccusedMasterID), `accused_record_b`, `match_score`, `contributing_signals` (JSON), `contradictory_signals` (JSON), `evidence_case_ids`, `method_version`, `review_state` (PENDING_REVIEW | CONFIRMED | REJECTED | NEEDS_MORE_EVIDENCE), `classification` = `POTENTIAL_ASSOCIATION`/`AI_DERIVED`.

### ResolvedIdentity + IdentityReviewEvent
Created **only** by human confirmation (ENT-003). `ResolvedIdentity` groups AccusedMasterIDs after review; `IdentityReviewEvent` is the immutable audit trail (`reviewer_user_id`, `decision`, `reason`, `timestamp`). Classification: `HUMAN_CONFIRMED`. No automatic merge path exists.

## Boundary rules
1. Derived tables never mutate source FIR tables.
2. Every derived row is traceable: run_id → method version → evidence case IDs.
3. `AI_DERIVED` values always carry confidence + model version.
4. UI must render classification visibly (UI-001 labeling system).
5. Deleting/regenerating derived data must not touch source rows.
