# MO Extraction Schema — v1 (`mo-schema-v1`)

Contract for AI enrichment of `CaseMaster.BriefFacts` (MO-001/#38, ADR-006).
Implementation: `backend/kavach/analytics/mo/schema.py`. Every extractor output
(QuickML LLM or rule-based fallback) is validated against this schema **before
persistence**; invalid output is rejected whole and the case is marked
`EXTRACTION_FAILED` — never partially trusted, never repaired in place.

## Rules

1. **UNKNOWN over invention** — every attribute accepts `"UNKNOWN"`; extractors must prefer it when the narrative lacks evidence.
2. **Closed vocabularies** — out-of-vocabulary values are rejected (no silent coercion).
3. **No invented attributes** — unknown keys fail validation (`extra="forbid"`).
4. **Classification** — output is `AI_DERIVED`; it is never merged into source tables and always carries `model_version` + `extractor`.
5. **escape_direction** is free text, display-only, and excluded from `SIMILARITY_ATTRIBUTES` (MO-004/#41).

## Attributes

Each attribute is `{value, confidence ∈ [0,1], source_span?: [start, end)}` (span indexes into the original BriefFacts text when the extractor can provide it).

| Attribute | Vocabulary |
|---|---|
| offender_count | integer ≥ 0 \| UNKNOWN |
| mobility | on_foot, motorcycle, car, autorickshaw, bicycle, public_transport, other, UNKNOWN |
| approach_method | mobile_approach, stationary_ambush, entry_breakin, deception, confrontation, other, UNKNOWN |
| crime_action | snatching, theft, burglary, robbery, assault, threat, fraud, other, UNKNOWN |
| target_type | gold_chain, mobile_phone, cash, vehicle, jewelry, property, person, other, UNKNOWN |
| escape_direction | free text \| UNKNOWN (display-only) |
| time_context | night, day, dawn_dusk, UNKNOWN |
| weapon_involved | yes, no, UNKNOWN |

Top-level: `case_master_id`, `schema_version` (must equal `mo-schema-v1`), `model_version`, `extractor` (`QUICKML_LLM` \| `RULE_BASED`).

## Worked example

Input (BriefFacts):

> "Two unknown persons travelling on a motorcycle approached the complainant and snatched a gold chain before escaping towards Tumakuru Road."

Valid output:

```json
{
  "case_master_id": 5501,
  "schema_version": "mo-schema-v1",
  "model_version": "quickml-mo-2026-07",
  "extractor": "QUICKML_LLM",
  "offender_count":   {"value": 2,               "confidence": 0.95, "source_span": [0, 19]},
  "mobility":         {"value": "motorcycle",    "confidence": 0.93, "source_span": [31, 41]},
  "approach_method":  {"value": "mobile_approach","confidence": 0.85},
  "crime_action":     {"value": "snatching",     "confidence": 0.97, "source_span": [76, 84]},
  "target_type":      {"value": "gold_chain",    "confidence": 0.96, "source_span": [87, 97]},
  "escape_direction": {"value": "Tumakuru Road", "confidence": 0.90, "source_span": [122, 135]},
  "time_context":     {"value": "UNKNOWN",       "confidence": 1.0},
  "weapon_involved":  {"value": "UNKNOWN",       "confidence": 1.0}
}
```

Note `time_context = UNKNOWN`: the narrative does not state a time — schema-conformant honesty, not a defect.

## Versioning

Additive changes only. A new vocabulary value or attribute bumps `SCHEMA_VERSION` (v2, …); similarity comparisons operate within the same major version (MO-004).
