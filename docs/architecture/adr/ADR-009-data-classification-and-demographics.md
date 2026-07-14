# ADR-009: Data Classification & Demographic Boundary

**Status:** Accepted (2026-07-14)

## Context
The schema contains complainant caste/religion/occupation. Misusing these as offender or area profiling features would be discriminatory and analytically wrong (complainant ≠ offender demographics). Judges will also probe whether AI output is presented as fact.

## Decision
1. Every data point in APIs/UI carries a classification: FACT / DERIVED_METRIC / STATISTICAL_INFERENCE / AI_DERIVED / POTENTIAL_ASSOCIATION / HUMAN_CONFIRMED (see derived-intelligence-schema.md).
2. `ComplainantDetails.ReligionID/CasteID/OccupationID` are prohibited as features in hotspot, trend, anomaly, risk, graph, and entity-resolution engines. Automated tests enforce the prohibition (feature manifest scanning).
3. Socio-economic correlation uses only external public area-level indicators (if genuinely available) and is worded as association, never causation.

## Alternatives considered
Using complainant demographics as "socio-economic" proxies: rejected — semantic and ethical error.

## Consequences
Victim-demographic vulnerability analysis (e.g., age-band victimization) is allowed only as descriptive statistics with sensitivity labeling.

## Risks
Feature creep re-introducing protected attributes → CI test asserts engine feature manifests exclude them.

## Revisit if
KSP provides an explicit, authorized analytical mandate with legal review.
