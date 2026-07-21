# CI/CD — auto-deploy to Catalyst (#84)

Pushes to `main` deploy automatically once one repository secret exists.

## Pipeline

```
push to main  →  CI (lint · tests · source-size gate · frontend build)
                      │ on success
                      ▼
              Deploy to Catalyst
                 1. regenerate synthetic dataset (fixed seed, ADR-011)
                 2. verify Data Store schema parity  ← fails if drifted
                 3. deploy AppSail (backend)
                 4. deploy Web Client (console)
                 5. smoke-test /health, /health/deps, /api/meta
```

- **CI must pass first** — `deploy.yml` triggers on `workflow_run` of the
  `CI` workflow, so a failing test never reaches the demo URLs.
- **Deploys the commit CI validated**, not whatever `main` drifted to.
- **Smoke-tested after deploy** — a "successful" deploy that then 503s is
  exactly the failure mode seen in #21, so the pipeline asserts the app
  actually serves before going green.
- `concurrency: catalyst-deploy` — deploys never overlap.
- Manual redeploy: **Actions → Deploy to Catalyst → Run workflow**.

## One-time setup (required — the pipeline skips cleanly until then)

GitHub runners have no `catalyst login` session, so the CLI authenticates
from a token instead.

### Recommended: reuse the existing CLI login (one command)

On the VM where `catalyst login` has already been run:

```bash
node scripts/catalyst/print_cli_token.js | gh secret set CATALYST_TOKEN
```

The credential `catalyst login` stored is the same kind of refresh token
`token:generate` mints, just encrypted with a machine-local key; the script
decrypts it to the portable form and writes it **straight into the secret**
— it never lands in a file, a log, or your shell history.

### Alternative: mint a fresh token

```bash
catalyst token:generate
```

⚠️ The device-code page **must be verified by the same Zoho account the
CLI is logged in as** (`catalyst whoami`). Verifying with a different
account fails with `TOKEN GENERATION FAILURE`, even if that account can
see the project — this bit us three times. Use a private window to avoid
the wrong auto-login.

2. Store it (never paste it into a file, issue, or PR):

   ```bash
   gh secret set CATALYST_TOKEN
   ```

Until the secret exists the deploy job **skips with a notice** rather than
failing — a red `main` caused by a missing credential is noise, not signal.

## Configuration

Project and org ids are identifiers, not secrets (they are recorded in
`project.md`), so they live in repository **variables** with a fallback
baked into the workflow. Override per environment:

| Variable | Default |
|---|---|
| `CATALYST_PROJECT_ID` | `42171000000017001` (AI-KSP) |
| `CATALYST_ORG_ID` | `60078928452` |
| `APPSAIL_URL` | the AppSail URL, baked into the SPA as `VITE_API_BASE` |

```bash
gh variable set CATALYST_PROJECT_ID --body 42171000000017001
```

## What is deliberately not automated

- **Data Store schema changes.** The pipeline runs `--verify` only; it never
  creates or alters tables on a deploy. Provisioning is an explicit,
  reviewed action (`provision_datastore.py`, optionally `--repair`).
- **Production promotion.** Only the Development environment is targeted;
  there is no production environment for this project yet.
