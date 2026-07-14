# ADR-005: Area-Level Risk Intelligence, No Individual Predictive Policing

**Status:** Accepted (2026-07-14)

## Context
The challenge asks for "Predictive Risk Scoring… High-Risk areas or emerging crime typologies". Individual-level prediction ("person X will offend") is ethically indefensible and unsupported by the data.

## Decision
Risk targets are geographic areas (district / station / grid cell) and crime categories only. Features: recent crime velocity, baseline deviation, spatial cluster density/growth, temporal recurrence, recurring MO frequency, anomaly frequency. Scores use a transparent versioned model with real feature contributions (no hard-coded driver percentages) and temporal holdout validation (no future leakage).

## Alternatives considered
Individual risk scoring: rejected outright. Black-box gradient boosting without explanation: rejected — explainability is a core feature.

## Consequences
UI copy says "area risk", drivers shown from actual contributions; limitations documented on every score.

## Risks
Sparse data yields unstable scores → minimum-support thresholds and confidence bands.

## Revisit if
Never for individual-level scoring; model family may evolve with validation evidence.
