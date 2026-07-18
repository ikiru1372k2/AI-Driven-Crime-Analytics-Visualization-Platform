# Frontend Hosting via Catalyst Web Client Hosting (CAT-006/#22)

The built React SPA deploys to Catalyst Web Client Hosting via
`make deploy-frontend` → `scripts/catalyst/deploy_frontend.sh`.

## Prerequisites

1. `npm i -g zcatalyst-cli` and `catalyst login`
2. Catalyst project (gated on RES-CATALYST-PROJECT-001, #16)
3. Environment (never committed — ADR-001):

   | Variable | Purpose |
   |---|---|
   | `CATALYST_PROJECT_ID` / `CATALYST_ORG_ID` | target project/org |
   | `VITE_API_BASE` | Catalyst API Gateway base URL, baked into the build |
   | `CATALYST_CLIENT_NAME` | optional, default `kavach-console` |

## Environment-aware API base

`frontend/src/lib/api.ts` resolves `VITE_API_BASE` at build time:
local dev falls back to the local FastAPI origin; hosted builds call the
API Gateway. The backend additionally honours `KAVACH_ALLOWED_ORIGINS`
(comma-separated) so the hosted origin passes CORS when the gateway is
cross-origin.

## SPA fallback / deep links

- Client state is hash-serialized (`#view=map&subhead=71&district=44…`),
  so shareable drill-downs reload correctly on any static host.
- The deploy stage also copies `index.html` → `404.html`, so path-style
  deep links (e.g. `/geo/district/44`, UI-*) fall back to the app shell.

## Verification checklist (hosted URL — pending live project)

- [ ] `make deploy-frontend` publishes to the Catalyst-hosted URL
- [ ] Deep links load via SPA fallback
- [ ] API calls hit the gateway from the hosted origin (CORS verified)
- [ ] Login end-to-end (needs Catalyst Authentication, CAT-003/#19 + #60)

## Status

Deploy path complete and reproducible from a clean checkout; live
publication awaits Catalyst project credentials
(RES-CATALYST-PROJECT-001). Custom domain mapping is out of scope (P3).
