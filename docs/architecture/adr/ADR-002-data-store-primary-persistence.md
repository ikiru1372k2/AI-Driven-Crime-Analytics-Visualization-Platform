# ADR-002: Catalyst Data Store as Primary Relational Persistence

**Status:** Accepted (2026-07-14)

## Context
The FIR ER schema is relational (26 documented tables, FK matrix). Catalyst Data Store is the mandated relational service.

## Decision
All source FIR tables and relational derived tables (IntelligenceRun, HotspotResult, TrendAlert, EntityResolutionCandidate, graph tables…) live in Catalyst Data Store, with physical column names preserving the documented ER names exactly. Semi-structured MO profiles live in Catalyst NoSQL.

## Alternatives considered
PostgreSQL (richer SQL, PostGIS): rejected as primary — submission validity. SQLite for local dev only: allowed as a dev fixture behind the repository layer, never the submitted store.

## Consequences
Spatial ops (clustering) run in the Python analytics runtime rather than in-database. Repository layer abstracts Data Store ZCQL/SDK. Bulk ingestion uses Data Store bulk APIs.

## Risks
ZCQL feature limits (no PostGIS, join limits) → analytics fetches scoped windows and computes in-process; documented per engine.

## Revisit if
Data volumes exceed in-process analytics feasibility.
