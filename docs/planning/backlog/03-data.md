=== ISSUE ===
key: EPIC-DATA
title: [EPIC] Crime Data Ingestion & Demo Dataset
labels: type:epic, area:data-platform, priority:p0
milestone: M1
estimate: -
risk: MEDIUM
blocked_by:
--- BODY ---
## Problem
No real FIR dataset was supplied — only the ER schema. The platform needs (a) a deterministic, schema-conformant synthetic dataset with embedded genuine statistical patterns (ADR-011) and (b) a dataset-agnostic ingestion/validation pipeline so a real dataset can replace the synthetic one without engine changes.

## Why it matters
Every engine computes on this data; the demo's credibility depends on outputs being genuinely discovered, not inserted.

## Challenge requirement
Foundational for all analytics requirements; directly supports "moving beyond manual records".

## Technical scope
Seeded generator, ingestion pipeline into Catalyst Data Store with validation + data-quality metrics.

## Out of scope
Demo choreography ({{DEMO-001}}), Data Store provisioning ({{CAT-002}}).

## Source data
Writes to all 26 source tables; generator parameters documented.

## Catalyst services
Data Store (bulk write), Stratus (raw dataset artifacts).

## Deliverables & success criteria
{{DATA-001}} generator (fixed seed → identical dataset); {{DATA-002}} validated ingestion with FK integrity + exclusion metrics.

## Risks
Synthetic realism; mitigated by pattern design review and documented limitations.

## Demo impact
Direct — the entire demo dataset.

## Child issues
{{DATA-001}}, {{DATA-002}}

=== ISSUE ===
key: DATA-001
title: [DATA] Deterministic synthetic FIR dataset generator with embedded ground-truth patterns
labels: type:data, area:data-platform, priority:p0, area:demo
milestone: M1
estimate: L
risk: MEDIUM
blocked_by: ER-001
--- BODY ---
## Summary
Build a seeded generator producing a schema-conformant Karnataka-realistic synthetic dataset (~5–10k cases + lookups + persons + arrests) that embeds documented ground-truth patterns the engines must later *discover*: a spatiotemporal robbery concentration (Peenya-like industrial area, night window), a recurring chain-snatching MO expressed in BriefFacts narratives, a fragmented accused identity across 3 districts, co-accused network structures, one behaviorally anomalous case, and a category spike in a recent window.

## Problem Statement
Without data, no engine can be built or validated. Random data would make the demo non-deterministic and validation impossible; hard-coded outputs are prohibited (ADR-011).

## Why This Matters
This dataset is simultaneously: dev fixture, validation ground truth (HOT-004/TREND-003/ENT-004 know what must be found), and demo substrate.

## Engineering Objective
`scripts/generate_dataset.py --seed 20260714 --out data/synthetic/` producing CSV per source table; identical output for identical seed.

## Source Data / ER Schema Mapping
Generates rows for ALL 26 documented tables with exact column names (driven by `schema-manifest.json` from {{ER-007}} conventions; manifest may be authored here first if ER-007 not yet merged). Every generated file carries a `# SYNTHETIC DEMO DATA` marker file alongside. CrimeNo follows the documented structured format (1-digit category + 4-digit district + 4-digit unit + 4-digit year + 5-digit serial, per-station/category/year serials); CaseNo = last 9 digits.

## ER Conformance Requirements
- No invented columns; nullable fields sometimes null (realistic missingness: ~4% coordinates missing, ages missing, etc. — rates documented)
- FK-valid by construction; a small documented set of deliberately dangling FKs to exercise data-quality reporting
- PersonID = A1/A2/A3 per case only
- BriefFacts narratives in English (dataset language decision documented per ADR-006)

## Ground-truth manifest
Generator writes `data/synthetic/ground_truth.json`: embedded pattern parameters (cluster center/radius/time-window/case IDs; MO template case IDs; identity-fragment accused record IDs; anomaly case ID; spike window/category/station). Consumed ONLY by validation suites — never by engines (enforced: engines have no import path to it).

## Catalyst Services
None at generation time; artifacts later uploaded to Stratus ({{DATA-002}}).

## Dependencies
Blocked by: {{ER-001}} · Blocks: {{DATA-002}}, {{HOT-004}}, {{TREND-003}}, {{ENT-004}}, {{DEMO-001}}

## Edge Cases
Midnight-spanning incidents; IncidentToDate spanning days; duplicate names across districts (deliberate, for ER testing); mixed gender codes m/f/t vs M/F/T; unicode names.

## Acceptance Criteria
- [ ] Two runs with the same seed produce byte-identical CSVs
- [ ] Output passes schema-manifest validation (all columns, types parseable)
- [ ] ground_truth.json enumerates every embedded pattern with involved record IDs
- [ ] Engines cannot import ground truth (lint rule/test)
- [ ] Dataset labelled SYNTHETIC in README + marker files
- [ ] Documented missingness/dangling-FK rates match generated data (validation script)

## Test Plan
Unit: determinism, manifest conformance, pattern-presence statistical self-check (e.g., cluster density in target window ≥ configured lift).

## Definition of Done
Standard DoD + ground-truth doc + ADR-011 cross-reference.

## Demo Evidence
`ground_truth.json` shown to judges when asked "how do you know the engine works?"

## Limitations / Non-Goals
Synthetic data does not represent real Karnataka crime statistics — stated on every demo screen footer ({{UI-001}}).

## References
ADR-011; matrix §1; {{ER-007}}.

=== ISSUE ===
key: DATA-002
title: [DATA] Ingestion + validation pipeline into Catalyst Data Store with data-quality metrics
labels: type:data, area:data-platform, area:catalyst, priority:p0
milestone: M1
estimate: M
risk: MEDIUM
blocked_by: DATA-001, CAT-002, ER-002, ER-003, ER-004, ER-005, ER-006
--- BODY ---
## Summary
Dataset-agnostic pipeline: CSV per source table → schema validation → FK integrity check → normalized load into Catalyst Data Store via repositories → data-quality report (row counts, exclusions, dangling FKs, missing coordinates/dates) persisted and exposed.

## Problem Statement
Engines must trust the store. Without a validation gate, malformed rows silently corrupt analytics; without exclusion metrics, "N cases analysed" claims are unverifiable.

## Why This Matters
The data-quality report is itself demo evidence ("17 records excluded for missing coordinates") and feeds every engine's limitations section.

## Engineering Objective
`backend/kavach/ingestion/` pipeline + CLI `python -m kavach.ingestion.load --src data/synthetic/`.

## Source Data / ER Schema Mapping
Reads all 26 table CSVs; validates against `schema-manifest.json`; loads via ER-002…006 repositories. All OBSERVED.

## ER Conformance Requirements
- Rejects unknown columns (fail-fast) — prevents invented fields entering the store
- Preserves raw values (no silent normalization); normalization happens in DERIVED views only
- Duplicate PK → reject row, count in report

## Catalyst Services
- Data Store: bulk row insert (documented batch limits handled with chunking + retry)
- Stratus: store raw source CSVs + data-quality report artifact

## Dependencies
Blocked by: {{DATA-001}}, {{CAT-002}}, {{ER-002}}–{{ER-006}} · Blocks: {{HOT-001}}, {{TREND-001}}, {{MO-002}}, {{GRAPH-001}}, {{ENT-001}}, {{ANOM-001}}, {{EVT-001}}, {{DEMO-001}}

## Data Flow
CSV → column/type validation → FK resolution pass → load (chunked, idempotent by PK) → DataQualityReport {table → {loaded, rejected(reason), dangling_fks, null_rates}} → Data Store + Stratus.

## Edge Cases
Partial load failure (resume idempotently); throttling/rate limits (backoff); BOM/encoding; empty tables; re-run (upsert semantics documented).

## Acceptance Criteria
- [ ] Full synthetic dataset loads with report matching DATA-001's documented rates (± exact counts)
- [ ] Deliberately corrupted fixture (unknown column, bad FK, dup PK) produces exact expected rejections
- [ ] Re-running the loader is idempotent (row counts unchanged)
- [ ] Report retrievable via API/CLI and stored in Stratus
- [ ] No silent value mutation (spot-check test: raw in == raw out)

## Test Plan
Integration vs local dev fixture; Catalyst smoke-load of one small table verified manually in CAT-002's environment; corrupted-fixture unit tests.

## Definition of Done
Standard DoD + data-quality report documented.

## Demo Evidence
Show report: totals + exclusions before opening the map.

## Limitations / Non-Goals
No streaming ingestion (EVT-001 covers event-driven single-record path).

## References
ADR-002; {{CAT-002}}; matrix §6.
