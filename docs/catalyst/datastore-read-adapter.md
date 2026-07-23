# Reading the app from the Catalyst Data Store (CAT-002 / PR-B)

Once the Data Store is seeded ([datastore-seeding.md](datastore-seeding.md)), the
app can read its rows **live** instead of the bundled CSVs, so an edit made in the
Zoho console shows up in the app within a short cache window — no redeploy. The
switch is a single environment flag; **the default is `csv`, so nothing changes
until you deliberately flip it.**

## How it works

`backend/kavach/api/datastore.py` reads whole source tables out of the Data Store
over OAuth REST and returns them as string-typed pandas DataFrames **shaped
exactly like the CSVs** `data.py` already reads — same columns, same string cells
(`""` for blanks). Every consumer of `data.py` (the analytics API, the graph
build, the engines) works unchanged; only the *source* of the rows changes.

- **Seam.** `data.py._read(name)` returns CSV rows or Data Store rows depending on
  `KAVACH_DATA_SOURCE`. `graph_store.py` materialises the tables to a temp dir and
  runs the existing CSV ingestion loader unchanged.
- **Auth.** A self-client refresh token mints a short-lived access token, cached
  process-wide — the same pattern as `catalyst/quickml.py`. No secrets are read
  from the repo (ADR-001); everything comes from the environment.
- **Transport.** Tables are read with ZCQL (`POST /baas/v1/project/{id}/query`),
  which caps a query at **300 rows**. A table is walked with **keyset pagination**
  on `ROWID` (`WHERE ROWID > <last> ORDER BY ROWID LIMIT 300`) — not `OFFSET`,
  which overlaps a row at page boundaries and would insert duplicates.
- **Liveness.** Each table is cached for `KAVACH_DATASTORE_TTL` seconds (default
  300). In CSV mode the cache is effectively forever, as before.

## Required scope (a separate token from QuickML)

The QuickML forecast token is scoped `QuickML.deployment.READ` and **cannot** read
the Data Store. The adapter reads via ZCQL, whose execute-query API needs the scope
**`ZohoCatalyst.zcql.CREATE`** — named `CREATE` even for `SELECT`, because it
executes a query resource. (`ZohoCatalyst.tables.rows.READ` only authorizes the
direct row-GET endpoint, which we don't use because it can't paginate.) Mint it as
its own console step:

1. Zoho API console (`https://api-console.zoho.in`, India DC) → your Self Client →
   **Generate Code** for scope `ZohoCatalyst.zcql.CREATE`, duration ~10 min.
2. Exchange the code (single-use, short-lived) for a **refresh token**:
   ```bash
   curl -s -X POST "https://accounts.zoho.in/oauth/v2/token" \
     -d grant_type=authorization_code -d client_id=... -d client_secret=... -d code=...
   ```
   Keep the `refresh_token` from the response (not the `access_token`).
3. Put it in the git-ignored `deploy.env` as `KAVACH_DATASTORE_REFRESH_TOKEN`
   (or let it fall back to `ZOHO_REFRESH_TOKEN` if that token carries the scope).

## Configuration

All read from the environment (see `backend/kavach/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `KAVACH_DATA_SOURCE` | `csv` | `csv` (bundled) or `datastore` (live). |
| `KAVACH_DATASTORE_REFRESH_TOKEN` | — | `ZohoCatalyst.zcql.CREATE` refresh token; falls back to `ZOHO_REFRESH_TOKEN`. |
| `KAVACH_DATASTORE_API_BASE` | `https://api.catalyst.zoho.in` | Catalyst DC base URL. |
| `KAVACH_DATASTORE_TTL` | `300` | Per-table cache lifetime, seconds. `0` disables caching. |

Reuses the existing `ZOHO_CLIENT_ID` / `ZOHO_CLIENT_SECRET` / `ZOHO_ACCOUNTS_URL`
and `CATALYST_PROJECT_ID` already set for QuickML.

> **AppSail note:** the runtime reserves the `CATALYST_*` env prefix — a
> `CATALYST_PROJECT_ID` key in `app-config.json`'s `env_variables` is rejected at
> deploy with `HTTP 400 … reserved keywords`. The deploy script therefore writes
> the id under the non-reserved alias `KAVACH_CATALYST_PROJECT_ID`, and
> `config.py` reads that first, then falls back to `CATALYST_PROJECT_ID` (used
> locally / in CI, where nothing is reserved).

## Enabling it

The safe rollout is **merge with the default (`csv`), then flip the flag in the
AppSail environment** once the read-scoped token is in place:

1. Confirm the Data Store is seeded and the read token is minted (above).
2. In the AppSail app environment, set `KAVACH_DATA_SOURCE=datastore` (plus the
   token if not already present) and restart.
3. Verify `GET /api/meta` returns the expected `total_cases` and district count.
   To roll back, set `KAVACH_DATA_SOURCE=csv` and restart — instant, no redeploy.

## Local verification

```bash
# CSV mode (default) — unchanged
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m pytest tests/api/test_datastore_adapter.py -q

# datastore mode against live rows (needs the read token in the environment)
KAVACH_DATA_SOURCE=datastore PYTHONPATH=. .venv/Scripts/python.exe -c \
  "from kavach.api import data; m = data.meta(); print(m['total_cases'], len(m['districts']))"
```

The adapter tests are **network-free** — the ZCQL transport is stubbed — so they
cover paging, coercion, reindex, cache, and the source selector without any
credentials.

## CSV parity notes

The Data Store returns typed values; the CSVs are all strings. The adapter coerces
each cell back to the CSV string form so downstream code is byte-identical:

- `None` (NULL) → `""` (matching `keep_default_na=False`).
- boolean `true`/`false` → `"1"`/`"0"` (the CSVs store BIT as `1`/`0`).
- bigint / double → `str(value)`.
- A column that is NULL for **every** row is omitted by ZCQL, so results are
  reindexed to the manifest's column list (blank-filled) — the CSV header always
  appears, so `df[[cols]]` never `KeyError`s.
