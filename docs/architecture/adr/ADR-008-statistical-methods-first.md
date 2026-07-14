# ADR-008: Statistical Methods Before Deep Learning

**Status:** Accepted (2026-07-14)

## Context
Judges will challenge every model. Deep learning without labels or volume is marketing, not analytics.

## Decision
Hotspots: DBSCAN/HDBSCAN + KDE with cyclic temporal encoding (sin/cos). Trends: rolling robust baselines (median/MAD), z-scores, EWMA; STL only where history suffices. Anomaly: IsolationForest/LOF + robust per-feature deviations. Risk: transparent weighted/linear model with temporal holdout. ML is introduced only where it beats the deterministic baseline on a real validation task.

## Alternatives considered
Deep spatiotemporal models (rejected: data volume, explainability); pure heuristics without statistics (rejected: not defensible).

## Consequences
Every threshold/alert is backed by a stated statistical quantity; no fake accuracy numbers — validation is via synthetic known-pattern tests and temporal holdout.

## Risks
Sparse series break baselines → minimum-history guards with explicit "insufficient history" states.

## Revisit if
A validated dataset shows a learned model materially outperforming the statistical baseline.
