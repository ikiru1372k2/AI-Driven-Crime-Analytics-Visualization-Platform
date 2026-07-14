# ADR-001: Catalyst-Native Architecture

**Status:** Accepted (2026-07-14)

## Context
Deployment via Catalyst by Zoho is mandatory for submission. Using third-party alternatives where a Catalyst capability exists may affect submission validity. Earlier drafts assumed Keycloak + PostgreSQL + Neo4j + external hosting.

## Decision
Every platform capability uses the matching Catalyst service: Data Store (relational), NoSQL (MO profiles), Stratus (artifacts), Authentication, API Gateway, Serverless Functions, AppSail (Python analytics runtime), QuickML (LLM/MO extraction), Signals + Event Functions, Circuits, Cron, SmartBrowz (reports), Push Notifications, Pipelines (CI/CD), Web Client Hosting (SPA). Third-party OSS is allowed only for algorithms (scikit-learn, NetworkX, pandas) and client visualization (MapLibre, Cytoscape.js, ECharts) where Catalyst provides no equivalent.

## Alternatives considered
External stack (Postgres/Keycloak/Neo4j/S3): rejected — submission risk, duplicate capability. Hybrid: rejected except documented gaps.

## Consequences
All persistence/API/auth code targets Catalyst SDKs; local dev needs a Catalyst project + credits; any Catalyst gap must be documented (gap, justification, risk, fallback) before an external service is introduced.

## Risks
Catalyst API limits/regional availability; QuickML capability uncertainty (fallback: rule-based extraction, documented in MO-002).

## Revisit if
A required capability is demonstrably unavailable in Catalyst during M2 verification.
