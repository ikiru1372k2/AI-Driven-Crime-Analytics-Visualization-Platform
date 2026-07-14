# ADR-004: Human-in-the-Loop Entity Resolution

**Status:** Accepted (2026-07-14)

## Context
No labelled match/non-match data exists; identity merging is high-consequence and legally sensitive.

## Decision
Pipeline = blocking-based candidate generation → explainable weighted feature scoring → review queue with states PENDING_REVIEW / CONFIRMED / REJECTED / NEEDS_MORE_EVIDENCE. AI never merges identities. Reviewer decisions are stored (IdentityReviewEvent) and become future training data (learning loop). No claim of continuous retraining unless implemented.

## Alternatives considered
Supervised matcher (no labels — rejected for MVP); unsupervised auto-merge (rejected — irreversible); no ER at all (rejected — key differentiator).

## Consequences
Every candidate exposes confidence, contributing signals, contradictory signals, evidence case IDs, method version. Review actions are audited.

## Risks
Weight tuning is heuristic → weights versioned + documented; threshold bands validated in ENT-004.

## Revisit if
Sufficient confirmed/rejected labels accumulate to train a supervised matcher (Zia AutoML).
