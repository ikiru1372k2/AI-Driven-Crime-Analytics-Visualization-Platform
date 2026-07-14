# ADR-003: Accused.PersonID Is Not a Global Person Identity

**Status:** Accepted (2026-07-14)

## Context
The ER document defines `Accused.PersonID` as "Accused Sorting like A1, A2, A3…" — a per-case ordering label. Misreading it as a state-wide person key would fabricate repeat-offender identities.

## Decision
`PersonID` is treated strictly as per-case ordering. Cross-FIR identity exists only as: `EntityResolutionCandidate` (AI_DERIVED, scored, explainable) and `ResolvedIdentity` (HUMAN_CONFIRMED, created only through the review workflow). Graph nodes for accused use `AccusedMasterID` (per-case record), never `PersonID`.

## Alternatives considered
Treat PersonID as person key: rejected — contradicts source semantics. Automatic fuzzy merge: rejected — irreversible identity errors (see ADR-004).

## Consequences
"Repeat offender tracking" is delivered as reviewed identity resolution, worded as "potential identity match", never "same person" pre-confirmation. Conformance tests assert no code path joins accused records across cases on PersonID.

## Risks
Judges may expect instant repeat-offender counts → demo shows the candidate→review→confirmed flow instead, which is more defensible.

## Revisit if
KSP supplies an authoritative person registry.
