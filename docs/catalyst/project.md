# Catalyst Project Record (CAT-001/#17)

Live project details — identifiers only, no secrets (ADR-001: credentials
live in the local CLI session / environment variables, never in the repo).

| Field | Value |
|---|---|
| Project name | **AI-KSP** |
| Project ID | `42171000000017001` |
| Org ID | `60078928452` |
| Data center | IN (`accounts.zoho.in` / `api.catalyst.zoho.in`) |
| Environment | Development (`ai-ksp-60078928452.development`) |
| Timezone | Asia/Kolkata |
| CLI | zcatalyst-cli 1.27.0, logged in (owner account) |

Local CLI workspace: `.catalyst-app/` (gitignored — holds `.catalystrc`
session state; recreate with `catalyst init --project 42171000000017001
--org 60078928452` in an empty dir).

## Capability probes — status so far

| Service | Status | Evidence |
|---|---|---|
| CLI auth / project list | VERIFIED | `catalyst whoami`, `project:list` show AI-KSP |
| **Data Store** | **VERIFIED (provisioned)** | 30 tables live; `--verify` → 30 ok / 0 absent / 0 drifted (#18) |
| **AppSail** | **VERIFIED (deployed)** | `kavach-analytics` serving; `/health` 200, full scientific stack imports in-cloud (#21) |
| **Web Client Hosting** | **VERIFIED (deployed)** | `kavach-console` serving the React console; zero console errors (#22) |
| API Gateway | AVAILABLE (disabled) | `apig:status` → DISABLED; enable via `apig:enable` (#20) |
| IaC export/import | VERIFIED | `iac:export` produced project template zip |
| CLI token (`token:generate`) | LIMITED | device-flow verification must be completed by the **same Zoho account as the CLI login**; needed only for CI (`CATALYST_TOKEN` env is supported by the CLI) |
| Catalyst SDK in AppSail | LIMITED | `zcatalyst_sdk.initialize(req=headers)` needs Catalyst headers, which are absent on direct AppSail URLs — they arrive via the authenticated path (#19/#20). Analytics use the bundled dataset meanwhile. |
| **Zia text analytics** | **VERIFIED (live)** | keyword-extraction + NER probed on AI-KSP 2026-07-21; NER returns character offsets **and** confidence scores. Powers MO extraction (#38). |
| NoSQL / QuickML / Signals / Circuits / Cron / Push / Auth | PENDING | probed during their issues (#39/#38/#71/#72/#73/#74/#19) |

## Live URLs

| Tier | URL |
|---|---|
| Console (Web Client) | https://ai-ksp-60078928452.development.catalystserverless.in/app/index.html |
| Analytics API (AppSail) | https://kavach-analytics-50044141253.development.catalystappsail.in |

Verified in-cloud: `/health` 200 · `/health/deps` → numpy 2.2.6, pandas 2.3.2,
sklearn 1.7.2, networkx 3.6.1 · `/api/meta` 2,236 cases · `/api/hotspots`,
`/api/trends`, `/api/overview` 200 · console renders live data, no console errors.

## Deployment gotchas (each cost a failed deploy — see #21/#22 commit)

1. `app-config.json` **must** carry `build_path`; the CLI validator rejects it otherwise.
2. Stack is `python_3_11` (underscored), not `python3.11`.
3. AppSail does **not** install `requirements.txt` — dependencies must be vendored into the bundle.
4. The startup command is **not** shell-expanded; `$X_ZOHO_CATALYST_LISTEN_PORT` must be read in code.
5. Web Client serves under `/app/` — build the SPA with `--base ./`.
6. `catalyst deploy` exits 0 even when it deploys nothing; assert on its output.

## Provisioning auth path (no separate token required)

The Data Store admin API accepts the logged-in CLI session's credential.
Table creation therefore runs on the VM through the CLI's authenticated
client — the `token:generate` device flow is only needed later for CI/CD
(GitHub Actions sets `CATALYST_TOKEN`).

## Next steps (in order)

1. #18 live: create 26 source + 4 derived tables, parity check, smoke insert
2. #15: load synthetic dataset into Data Store
3. #21/#22: `catalyst deploy` backend (AppSail) + frontend (Web Client)
4. #84 CI/CD: `catalyst token:generate` (verify with the CLI's own account),
   store as `CATALYST_TOKEN` repo secret, Pipelines/Actions deploy on `main`
