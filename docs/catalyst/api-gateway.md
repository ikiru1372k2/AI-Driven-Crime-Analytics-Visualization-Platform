# API Gateway (CAT-004/#20)

Status: **enabled on the project; rule deployment is blocked.** This page
records exactly what is verified and what is not, because the tooling
reports success in a case where nothing was applied.

## What is verified

| Item | Status | Evidence |
|---|---|---|
| API Gateway enabled on AI-KSP | ✅ | `catalyst apig:status` → `ENABLED` |
| Rules committed as reviewable code | ✅ | `catalyst/catalyst-user-rules.json` |
| Reproducible deploy + verification script | ✅ | `scripts/catalyst/deploy_gateway.sh` |
| Integration matrix (auth/no-auth per group) | ✅ | `scripts/catalyst/verify_gateway.sh` |
| `/api/*` resolving **through** the gateway | ❌ | see below |

## The blocker (reproduced, not assumed)

`catalyst deploy --only apig` prints **`DEPLOYMENT SUCCESSFUL: API Gateway`**
and exits 0, but the server stores none of the submitted rules. Reading the
rules back afterwards returns only the auto-generated `Login Redirect`:

```
$ catalyst deploy --only apig --org <org>
✔ DEPLOYMENT SUCCESSFUL: API Gateway
$ GET /baas/v1/project/<id>/api-gateway/api   →   [ { "name": "Login Redirect", … } ]
```

This was reproduced with **three** rule variants, ruling out a bad payload
for the AppSail target specifically:

1. `target: appsail`, `target_id` = app name → dropped
2. `target: appsail`, `target_id` = numeric app id → dropped
3. `target: client` (a target the CLI explicitly documents as valid) → **also dropped**

Because even a documented-valid target does not persist, the failure is in
the rule-upload path, not in the AppSail routing idea. Requests to
`https://<project>.development.catalystserverless.in/api/meta` therefore
return `INVALID_URL_PATTERN` (404) — no rule exists to match them.

Direct REST attempts (`POST /api-gateway/api`) return
`400 Check if the input json is proper` for every shape tried; the CLI
uploads a **multipart config file** via `PUT`, which is the only sanctioned
path and is the one that silently no-ops.

Note the CLI's own validator lists valid targets as `client`,
`advancedio`, `basicio` — **AppSail is not among them**. Rules with an
explicit `target_endpoint` skip that validation, which is why an
`appsail` rule is accepted locally and then discarded server-side. Whether
this Catalyst version/plan supports fronting AppSail with the gateway is
the open question.

## To finish this issue

The rules are ready; they need to be applied by a path that works:

1. **Catalyst console** → Serverless → API Gateway → add the two rules from
   `catalyst/catalyst-user-rules.json` (source `/api/(.*)` → target the
   `kavach-analytics` AppSail, `ANY`; plus the `/health` rule), then run:
   ```bash
   GATEWAY_URL=https://ai-ksp-60078928452.development.catalystserverless.in \
     scripts/catalyst/verify_gateway.sh
   ```
2. If the console offers no AppSail target, the gateway cannot front AppSail
   on this plan. The fallback is to route through a thin Catalyst Function,
   which adds a hop and its own limits — worth raising with Zoho support
   before adopting.

## Throttling (configured, not yet in force)

Committed with the rules, applied when they are:

| Rule | Overall | Per IP |
|---|---|---|
| `kavach_api` (`/api/*`) | 600 / minute | 120 / minute |
| `kavach_health` (`/health*`) | 120 / minute | 30 / minute |

## Current production posture — read this before demoing

Until the gateway fronts the API, the console calls AppSail directly
(`VITE_API_BASE`).

**The currently deployed build predates #19 and does not enforce the new
auth model.** Measured against the live AppSail on 2026-07-19:

| Route (no credentials) | Live response | After redeploying #19 |
|---|---|---|
| `/api/v1/audit` | `403` (old header check) | `401` |
| `/api/v1/graph/subgraph` | `500` | `401` |

So the protection described in `auth-and-roles.md` exists **in the code**,
not yet **in the deployment**. Redeploy the backend once #19 merges:

```bash
CATALYST_PROJECT_ID=… CATALYST_ORG_ID=… scripts/catalyst/deploy_backend.sh
```

The `500` on `/api/v1/graph/subgraph` is a separate live-only defect (the
graph context builds fine locally) and needs its own investigation — it is
not caused by the gateway work.

Once redeployed, the app-level enforcement is real defence — what the
gateway would add on top is a *central* enforcement point plus throttling.

## Related finding: project ids must be strings

`catalyst.json` written with an unquoted `project_id` is silently corrupted
(`42171000000017001` → `42171000000017000`): the value exceeds JavaScript's
safe-integer range. Always quote it. Fixed in the deploy scripts and the
CI workflow.
