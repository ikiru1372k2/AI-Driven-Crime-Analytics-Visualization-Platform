# ADR-011: Demo Data Strategy

**Status:** Accepted (2026-07-14)

## Context
No real FIR dataset is supplied — only the ER schema. The demo must be deterministic, but analytics must genuinely compute results (no hard-coded intelligence cards).

## Decision
A deterministic, seeded synthetic dataset generator (DATA-001) produces schema-conformant records clearly labelled SYNTHETIC/DEMO. The seed data intentionally embeds *statistical ground truth patterns* — e.g., a genuine robbery concentration in a Peenya-like area/time window, a recurring chain-snatching MO across narratives, a fragmented accused identity across districts, one behaviorally anomalous case. The engines must **discover** these patterns; results are never inserted directly. Expected outputs are documented (DEMO-002) so the demo is reproducible, and a reset script restores the exact dataset.

## Alternatives considered
Hard-coded demo cards (prohibited — indefensible); fully random data (rejected — non-deterministic demo); scraped real crime data (rejected — provenance/privacy risk).

## Consequences
Every demo number is reproducible: seed → records → engine → evidence case IDs. Judges can trace any card to CaseMasterIDs.

## Risks
Overfitting the demo narrative → engines contain zero demo-specific constants; patterns exist only in data.

## Revisit if
Organizers release a real/sample dataset — generator is then bypassed by the ingestion pipeline (DATA-002), which is dataset-agnostic.
