# ADR-007: Evidence-Backed Derived Graph (No Graph Database)

**Status:** Accepted (2026-07-14)

## Context
Network/link analysis is a challenge requirement. A dedicated graph DB (Neo4j) adds submission risk and infrastructure weight without analytical necessity at hackathon scale.

## Decision
The association graph is a deterministic projection of relational records into CrimeGraphNode/CrimeGraphEdge tables in Catalyst Data Store. Every edge carries `evidence_case_id` + `derivation` — unexplained edges are prohibited. Metrics (components, degree/betweenness centrality, communities, Jaccard) run in-process with NetworkX. Interpretation language is constrained: "high-connectivity bridge in the observed case-association graph", never "gang leader".

## Alternatives considered
Neo4j (rejected: ADR-001, scale unneeded); ad-hoc joins in API (rejected: no provenance, recomputation cost).

## Consequences
Graph rebuilds are reproducible per run_id; UI reads persisted projection.

## Risks
Betweenness cost on large graphs → computed per connected component with size caps, documented.

## Revisit if
Graph exceeds in-memory practicality.
