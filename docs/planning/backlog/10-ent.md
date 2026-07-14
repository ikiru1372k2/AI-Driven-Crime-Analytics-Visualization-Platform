=== ISSUE ===
key: EPIC-ENT
title: [EPIC] Cross-FIR Entity Resolution (Human-in-the-Loop)
labels: type:epic, area:entity-resolution, area:ai, priority:p0
milestone: M6
estimate: -
risk: MEDIUM
blocked_by:
--- BODY ---
## Problem
Accused records are per-case; the same real person may appear as "Ravi Kumar/29/M" (FIR 101), "Ravi K/30/M" (FIR 205), "Ravi Kumar S/30/M" (FIR 410) across jurisdictions. PersonID cannot resolve this (per-case ordering, ADR-003). Cross-FIR identity fragmentation blocks repeat-offender intelligence.

## Why it matters
C2-R6 (repeat offender tracking) — the strongest differentiator, delivered defensibly: explainable candidates + human review, never automatic merge (ADR-004). Demo step D5.

## Challenge requirement
C2-R6, C2-R5 support.

## Technical scope
Blocking-based candidate generation, explainable feature scoring, review workflow with audit + feedback storage, validation suite.

## Out of scope
Supervised matcher (no labels — future once feedback accumulates); automatic merging (prohibited).

## Source data
Accused (name/age/gender per case), CaseMaster (geography/time/category context), ArrestSurrender (cross-district arrests), graph overlap ({{GRAPH-001}}), MO similarity ({{MO-004}}).

## Catalyst services
Data Store, AppSail, Authentication (review roles).

## Deliverables & success criteria
Ground-truth fragmented identity surfaces as top candidate; same-name-different-person control does NOT confirm-score; review flow audited; feedback persisted.

## Risks
Heuristic weights — versioned, threshold bands validated ({{ENT-004}}).

## Demo impact
D5 — candidate card with signals/contradictions + review action.

## Child issues
{{ENT-001}}, {{ENT-002}}, {{ENT-003}}, {{ENT-004}}

=== ISSUE ===
key: ENT-001
title: [FEATURE] Entity resolution candidate generation with blocking (no O(N²))
labels: type:feature, area:entity-resolution, priority:p0
milestone: M6
estimate: M
risk: MEDIUM
blocked_by: ER-003, DATA-002
--- BODY ---
## Summary
Generate candidate accused-record pairs for identity scoring using blocking: normalized-name token/prefix keys + phonetic keys + gender + age band, avoiding full pairwise comparison while provably retaining ground-truth matches.

## Problem Statement
Comparing every accused pair is O(N²) and infeasible/noisy. Blocking must cut candidate volume by orders of magnitude without dropping true fragments.

## Source Data / ER Schema Mapping (OBSERVED)
Accused: AccusedMasterID, AccusedName, AgeYear, GenderID, CaseMasterID. Same-case pairs excluded (they are co-accused, not identity candidates).

## ER Conformance Requirements
- No PersonID usage (guard)
- Name normalization is DERIVED (casefold, punctuation strip, token sort, transliteration-stable phonetics) — raw names untouched

## Technical Design
Block keys per record: (a) first-token prefix (4 chars, normalized), (b) phonetic key (double metaphone; documented Indic-name limitation), (c) gender-normalized, (d) age band (±5y overlapping bands). Candidate = pair sharing ≥1 name-based key AND compatible gender AND overlapping age band (missing age → pass with flag). Persist CandidatePair {record_a, record_b, block_keys_hit}.

## Dependencies
Blocked by: {{ER-003}}, {{DATA-002}} · Blocks: {{ENT-002}}

## Edge Cases
Missing age (don't block out); gender code variants; single-token names; extremely common names (block size cap with escalation to stricter key, documented); unicode/transliteration variants.

## Acceptance Criteria
- [ ] All DATA-001 ground-truth fragment pairs appear in candidates (100% blocking recall on ground truth)
- [ ] Candidate volume ≤ 1% of full pairwise count on synthetic dataset (documented actual figure)
- [ ] Same-case pairs excluded
- [ ] Deterministic candidate set

## Test Plan
Unit: normalization/keys; validation: blocking recall vs ground truth; volume report.

## Definition of Done
Standard DoD + ER gate.

## Demo Evidence
Candidate counts panel ("2.1M pairs reduced to 8.4k candidates").

## Limitations / Non-Goals
Scoring (ENT-002); Kannada-script names out of v1 scope (documented).

## References
ADR-003; ADR-004.

=== ISSUE ===
key: ENT-002
title: [FEATURE] Explainable identity match scoring: weighted features, contributing & contradictory signals
labels: type:feature, area:entity-resolution, area:ml, priority:p0, risk:model
milestone: M6
estimate: M
risk: MEDIUM
blocked_by: ENT-001
--- BODY ---
## Summary
Score candidate pairs with a versioned, weighted, explainable model over: name similarity (token-set + Jaro-Winkler + phonetic), age compatibility (drift-tolerant), gender consistency, geographic case overlap, temporal compatibility, crime-category overlap, co-accused graph overlap ({{GRAPH-001}} Jaccard), MO similarity ({{MO-004}}) — emitting match_score plus itemized contributing AND contradictory signals.

## Problem Statement
Blocking yields pairs but no defensible judgment. Score must be explainable per signal — a bare "0.87" is prohibited; contradictions (age gap 15y) must be surfaced, not averaged away silently.

## Algorithm / Analytical Method
- Feature vector per pair (each feature ∈ [0,1] with MISSING state)
- Score = Σ w_i·f_i / Σ w_i over non-missing (weights `ent-score v1`, documented rationale: name 0.30, age 0.15, gender 0.10 hard-contradiction rule below, geography 0.10, temporal 0.05, category overlap 0.10, co-accused overlap 0.10, MO similarity 0.10)
- Hard contradiction rules: conflicting gender → cap score at 0.3 + contradictory signal; age gap > 8y (adjusted for case-date gap) → strong contradictory signal
- Bands (versioned): ≥0.85 STRONG, 0.70–0.85 MODERATE, 0.55–0.70 WEAK → below: discard (not persisted)
- Temporal compatibility: implied birth-year consistency across case dates
- No supervised training claimed (no labels — ADR-004); reviewer feedback stored for future training
- Failure/limitation: transliteration variance, common names — top documented limitations

## Source Data / ER Schema Mapping
Features DERIVED from OBSERVED Accused/CaseMaster/ArrestSurrender + DERIVED graph/MO inputs. Output: EntityResolutionCandidate rows (classification POTENTIAL_ASSOCIATION / AI_DERIVED) with review_state=PENDING_REVIEW.

## Dependencies
Blocked by: {{ENT-001}} · Related: {{GRAPH-002}}, {{MO-004}} (features degrade gracefully to MISSING if absent) · Blocks: {{ENT-003}}, {{ENT-004}}

## Persistence Design
candidate_id, record pair, match_score, band, contributing_signals JSON [{signal, value, weight, contribution}], contradictory_signals JSON, evidence_case_ids (both records' cases), method_version, review_state.

## Edge Cases
Identical common names different districts (geography/temporal features low → MODERATE at best — fixture); missing age both sides; one record with rich MO one without (MISSING, renormalized); candidate re-scoring on new model version (new rows, review state preserved by pair key).

## Acceptance Criteria
- [ ] Ground-truth fragment pairs score STRONG/MODERATE with name+age+geo contributions itemized
- [ ] Same-name-different-person control pairs score < STRONG with visible contradictions
- [ ] Conflicting gender cap enforced (test)
- [ ] Every persisted candidate has non-empty contributing_signals and evidence_case_ids
- [ ] Output wording = "POTENTIAL IDENTITY MATCH" everywhere (copy test)

## Test Plan
Unit per feature; validation vs ground truth + controls ({{ENT-004}}); determinism.

## Definition of Done
Standard DoD + weights doc committed.

## Demo Evidence
D5 candidate card: 87% with signal list and contradiction list.

## Limitations / Non-Goals
No merge; no supervised accuracy claims.

## References
ADR-003; ADR-004; {{ENT-001}}.

=== ISSUE ===
key: ENT-003
title: [FEATURE] Identity review workflow: states, API, audit, feedback persistence, ResolvedIdentity
labels: type:feature, area:entity-resolution, area:auth, priority:p0
milestone: M6
estimate: M
risk: LOW
blocked_by: ENT-002, CAT-003, PROV-003
--- BODY ---
## Summary
Human-in-the-loop review: authorized reviewers move candidates through PENDING_REVIEW → CONFIRMED / REJECTED / NEEDS_MORE_EVIDENCE; CONFIRMED creates/extends a `ResolvedIdentity` (HUMAN_CONFIRMED) grouping AccusedMasterIDs; every decision writes IdentityReviewEvent (audit) and feedback rows for future model training.

## Problem Statement
Candidates without a review path are dead ends; automatic merging is prohibited (ADR-004). The learning loop (AI candidate → human review → feedback dataset) needs durable storage.

## User Story
As an authorized investigator, I want to confirm or reject potential identity matches with recorded reasoning, so that repeat-offender intelligence is human-validated and auditable.

## API Contract
- `GET /api/v1/identity/candidates?state=&band=&scope=` (scoped: reviewer sees candidates whose cases intersect their scope)
- `POST /api/v1/identity/candidates/{id}/review` {decision, reason} — role: INVESTIGATOR/SUPERVISOR; writes audit event
- `GET /api/v1/identity/resolved/{id}` → grouped records + confirming events
- Conflict rules: candidate joining records already in different ResolvedIdentities → NEEDS_MORE_EVIDENCE auto-flag (no silent merge of groups)

## Source Data / ER Schema Mapping
EntityResolutionCandidate (AI_DERIVED) → ResolvedIdentity (HUMAN_CONFIRMED) → members reference Accused.AccusedMasterID (OBSERVED). Source Accused rows never mutated.

## Catalyst Services
Data Store; Authentication (roles); audit via {{PROV-003}}.

## Dependencies
Blocked by: {{ENT-002}}, {{CAT-003}}, {{PROV-003}} · Blocks: {{UI-007}}

## Edge Cases
Concurrent reviews (optimistic lock); un-confirm (SUPERVISOR-only reversal with audit, group recomputed); transitive chains A≈B, B≈C reviewed separately (group union only through confirmed pairs).

## Acceptance Criteria
- [ ] Decision transitions enforced (invalid transition → 409)
- [ ] CONFIRMED produces ResolvedIdentity with member records and HUMAN_CONFIRMED classification
- [ ] Every decision → exactly one audit event + one feedback row {pair features, decision}
- [ ] Unauthorized role cannot review (403 test)
- [ ] Source Accused table byte-identical before/after reviews (test)

## Test Plan
Unit: state machine. Integration: full review flow with two roles. Security: authz matrix.

## Definition of Done
Standard DoD.

## Demo Evidence
D5: reviewer confirms candidate → graph shows HUMAN_CONFIRMED identity link distinctly.

## Limitations / Non-Goals
No automatic retraining (feedback stored only — honest wording shipped).

## References
ADR-004; {{PROV-003}}.

=== ISSUE ===
key: ENT-004
title: [TEST] Entity resolution validation suite (ground truth, same-name controls, thresholds, no-auto-merge)
labels: type:test, area:entity-resolution, area:ml, priority:p0
milestone: M6
estimate: S
risk: LOW
blocked_by: ENT-002, DATA-001
--- BODY ---
## Summary
Validation: ground-truth fragmented identity recovered in top candidates; same-name-different-person controls not STRONG; spelling/age-drift fixtures; missing/contradictory attribute handling; threshold band distribution report; assertion that no code path merges identities automatically.

## Acceptance Criteria
- [ ] Ground-truth fragment pairs: 100% present, ≥1 STRONG band
- [ ] Same-name controls (DATA-001 deliberate duplicates): 0 STRONG without corroborating signals
- [ ] Age-drift (29→30 across years) fixture scores compatible; 15y gap produces contradiction
- [ ] Band distribution report generated into docs/analytics/validation.md
- [ ] Static/behavioral test: no write path to ResolvedIdentity outside review API
- [ ] Suite in CI

## Dependencies
Blocked by: {{ENT-002}}, {{DATA-001}} · Blocks: DoD of {{ENT-002}}

## Definition of Done
Green in CI; validation doc updated.

## Demo Evidence
Cited when judges probe false-merge risk.

## References
ADR-004; DATA-001 ground truth.
