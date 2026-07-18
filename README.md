# KAVACH AI — Karnataka Crime Intelligence & Analytical Platform

[![CI](https://github.com/ikiru1372k2/AI-Driven-Crime-Analytics-Visualization-Platform/actions/workflows/ci.yml/badge.svg)](https://github.com/ikiru1372k2/AI-Driven-Crime-Analytics-Visualization-Platform/actions/workflows/ci.yml)

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

## Prerequisites

| Tool | Notes |
|---|---|
| Python 3.11+ | Backend (FastAPI / uvicorn) |
| Node.js 20+ / npm | Frontend (Vite + React) |
| Make | Optional; wraps common commands |

## How to run (local development)

You need **two terminals**: backend on port **8000**, frontend on port **5173**.

### 1. Backend API

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

From the **repo root** (with the venv still active):

```bash
make backend-dev
```

Or equivalently:

```bash
cd backend
uvicorn kavach.api.main:app --reload --port 8000
```

| Check | URL |
|---|---|
| Health | http://127.0.0.1:8000/health |
| OpenAPI docs | http://127.0.0.1:8000/docs |

### 2. Frontend console

In a **second terminal**:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** (not a LAN IP — Vite binds to `127.0.0.1` by default).

The UI calls the API at `http://127.0.0.1:8000` by default. Override if needed:

```bash
VITE_API_BASE=http://127.0.0.1:8000 npm run dev
```

### Make targets (repo root)

| Command | What it does |
|---|---|
| `make backend-dev` | Start FastAPI on `:8000` with reload |
| `make frontend-dev` | Start Vite on `:5173` |
| `make lint` | Ruff check (`backend/`) |
| `make test` | Pytest (`backend/`) |
| `make build` | Production frontend build |

### Troubleshooting

| Symptom | Fix |
|---|---|
| `Backend unreachable — Failed to fetch` | Start the backend on **8000**; confirm http://127.0.0.1:8000/health |
| `ERR_CONNECTION_REFUSED` on `192.168.x.x:5173` | Use **http://localhost:5173** — Vite listens on localhost only |
| Wrong API host/port | Set `VITE_API_BASE` when starting the frontend |

> Demo data is **synthetic** ([ADR-011](docs/architecture/adr/ADR-011-demo-data-strategy.md)). The yellow banner in the UI is expected.

## Engineering delivery

Work is tracked as GitHub Milestones (M0–M10), Epics and fully-specified issues — see the [delivery plan](docs/planning/delivery-plan.md) and the issue tracker. Every analytics issue must pass the [ER Schema Conformance Gate](docs/schema/er-conformance-matrix.md#6-conformance-gate-checklist) before closing.

> All demo data is **synthetic** (deterministic generator, [ADR-011](docs/architecture/adr/ADR-011-demo-data-strategy.md)); analytics genuinely compute every displayed result — nothing is hard-coded.
