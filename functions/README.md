# Catalyst Functions

Thin Catalyst Serverless / Event / Circuit-step functions (ADR-010 boundary):
heavy analytics lives in `backend/` (AppSail); functions here only handle
events (Signals triggers, EVT-001), Circuits steps (EVT-002) and Cron entry
points (EVT-003), delegating to AppSail endpoints.

Populated from CAT-001 findings (runtime choice + scaffolding conventions).
