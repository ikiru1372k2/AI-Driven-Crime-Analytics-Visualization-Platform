# ADR-006: Structured MO Schema for BriefFacts AI Enrichment

**Status:** Accepted (2026-07-14)

## Context
`CaseMaster.BriefFacts` is the only unstructured narrative field. Free-form LLM output must not become analytical truth.

## Decision
MO extraction uses a fixed, versioned schema (offender_count, mobility, approach_method, crime_action, target_type, escape_direction, time_context — finalized in MO-001) with closed vocabularies per attribute where feasible. Every attribute carries value + confidence + model_version (+ source span where available). `UNKNOWN` is a first-class value; invention is prohibited. Output is validated against the schema before persistence; invalid output is rejected and logged, never partially trusted.

## Alternatives considered
Free-form summaries (rejected — not comparable/analyzable); classical NER only (kept as fallback if QuickML unavailable).

## Consequences
MO similarity operates over the structured schema; UI labels all MO data AI_DERIVED with confidence.

## Risks
LLM hallucination → schema validation + UNKNOWN preference; Kannada text → scope decided by actual dataset language, documented.

## Revisit if
Schema needs new attributes — additive versioned change only.
