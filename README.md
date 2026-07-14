# KAVACH AI — Karnataka Crime Intelligence & Analytical Platform

**From Fragmented FIR Records to Connected, Explainable and Proactive Crime Intelligence.**

KSP Datathon 2026 · Challenge 2 — *AI-Driven Crime Analytics & Visualization Platform* · Deployed on **Catalyst by Zoho** (mandatory, [ADR-001](docs/architecture/adr/ADR-001-catalyst-native-architecture.md)).

## What this is

A state-level crime intelligence platform that turns Karnataka Police FIR records into:

1. **DETECT** — spatiotemporal crime hotspots (DBSCAN/HDBSCAN + cyclic time encoding)
2. **UNDERSTAND** — AI-extracted Modus Operandi from FIR `BriefFacts` (Catalyst QuickML, structured schema, UNKNOWN-preferring)
3. **CONNECT** — evidence-backed criminal association graphs (every edge carries its FIR)
4. **RESOLVE** — human-in-the-loop cross-FIR identity resolution (potential matches, never automatic merges)
5. **FLAG** — explained behavioral anomaly detection
6. **FORECAST** — explainable area-level risk intelligence (no individual predictive policing)
7. **EXPLAIN** — provenance on every result: method, version, window, evidence case IDs
8. **ACT** — event-driven pipeline: Signals → Event Functions → Circuits → alerts

## Repository map

| Path | Contents |
|---|---|
| `backend/` | Python analytics runtime (FastAPI → Catalyst AppSail): domain (exact ER mappings), repositories, provenance, engines, API |
| `functions/` | Thin Catalyst Serverless/Event/Circuit functions |
| `frontend/` | React intelligence console (Catalyst Web Client Hosting) |
| `docs/schema/` | **[ER Conformance Matrix](docs/schema/er-conformance-matrix.md)** (authoritative FIR schema catalogue) + [derived-intelligence boundary](docs/schema/derived-intelligence-schema.md) |
| `docs/architecture/` | [Target architecture](docs/architecture/target-architecture.md) + ADR-001…011 |
| `docs/traceability/` | [Challenge traceability matrix](docs/traceability/challenge-traceability.yaml) |
| `docs/planning/` | [Delivery plan](docs/planning/delivery-plan.md), backlog sources, [issue map](docs/planning/issue-map.json) |
| `scripts/` | GitHub backlog tooling; dataset/demo scripts (as issues land) |

The supplied Police FIR ER design document is kept locally under `schema/` and is **not committed** (marked confidential by its issuer); the committed conformance matrix is the working catalogue.

## Development

```bash
# backend
cd backend && python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
make lint test backend-dev   # from repo root

# frontend
cd frontend && npm install
npm run dev
```

## Engineering delivery

Work is tracked as GitHub Milestones (M0–M10), Epics and fully-specified issues — see the [delivery plan](docs/planning/delivery-plan.md) and the issue tracker. Every analytics issue must pass the [ER Schema Conformance Gate](docs/schema/er-conformance-matrix.md#6-conformance-gate-checklist) before closing.

> All demo data is **synthetic** (deterministic generator, [ADR-011](docs/architecture/adr/ADR-011-demo-data-strategy.md)); analytics genuinely compute every displayed result — nothing is hard-coded.
