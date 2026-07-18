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
| Data Store (API reachability) | VERIFIED | `ds:export` + admin `GET /table` succeed (0 tables — provisioning is #18) |
| API Gateway | AVAILABLE (disabled) | `apig:status` → DISABLED; enable via `apig:enable` (#20) |
| AppSail build stacks | AVAILABLE | CLI config lists python3_9/3_10/3_11, node12–24 |
| IaC export/import | VERIFIED | `iac:export` produced project template zip |
| CLI token (`token:generate`) | LIMITED | device-flow verification must be completed by the **same Zoho account as the CLI login**; needed only for CI (`CATALYST_TOKEN` env is supported by the CLI) |
| Table admin API via CLI session | VERIFIED | authenticated `GET /baas/v1/project/{id}/table` returns success |
| NoSQL / QuickML / Signals / Circuits / Cron / Push / Auth | PENDING | probed during their issues (#39/#38/#71/#72/#73/#74/#19) |

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
