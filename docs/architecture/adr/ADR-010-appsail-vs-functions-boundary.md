# ADR-010: AppSail vs Serverless Functions Boundary

**Status:** Accepted (2026-07-14)

## Context
Analytics needs Python with scientific libraries (scikit-learn, NetworkX, pandas) and non-trivial execution time. Catalyst Functions suit lightweight event/API logic; AppSail hosts a full managed/custom runtime.

## Decision
- **AppSail (Python/FastAPI):** analytics engines, analytics/read APIs, graph computation, entity resolution, risk scoring.
- **Functions:** event functions (Signals triggers), thin integration glue, Circuits step functions, cron entry points that invoke AppSail endpoints.
- **Web Client Hosting:** the React SPA.

## Alternatives considered
Everything in Functions (rejected: scientific-lib cold-start/runtime limits); everything in AppSail (rejected: loses event-driven Catalyst services showcase).

## Consequences
One deployable analytics service with clear module structure; event flow demonstrates Signals/Event Functions/Circuits explicitly.

## Risks
AppSail runtime limits for heavy jobs → jobs are windowed/scoped; long jobs run via Cron in slices.

## Revisit if
Runtime verification in M2 (CAT-005) contradicts assumptions — fallback boundaries documented there.
