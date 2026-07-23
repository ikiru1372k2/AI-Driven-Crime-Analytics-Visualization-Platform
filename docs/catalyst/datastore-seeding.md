# Seeding the Catalyst Data Store from the synthetic CSVs (CAT/seed)

`scripts/catalyst/seed_datastore.py` bulk-loads every source CSV from
`data/synthetic` into the matching Data Store table, so the Zoho console becomes
the live, editable source of truth the app reads from (PR-B). It is a **local,
one-shot operator tool** — not part of the AppSail runtime.

It builds on `provision_datastore.py`: same authenticated transports
(`--via-cli` CLI session, or `CATALYST_OAUTH_TOKEN`), same retry/backoff, and the
same schema plan (for per-column type coercion). Table order is the ingestion
loader's FK-dependency order (parents before children).

## Prerequisites

1. **Schema provisioned.** Run `provision_datastore.py` first (idempotent):
   ```bash
   python scripts/catalyst/provision_datastore.py --via-cli .catalyst-build/appsail \
       --project-id 42171000000017001 --verify
   ```
2. **Authenticated.** Either `catalyst login` (then use `--via-cli <app-dir>`,
   an app directory containing `catalyst.json`), or export
   `CATALYST_PROJECT_ID` / `CATALYST_ORG_ID` / `CATALYST_OAUTH_TOKEN`
   (never committed — ADR-001).
3. **A Live project.** The seed refuses to run against a dev-tier project
   (see quota note). The live project `AI-KSP` (`42171000000017001`) is `Live`.
4. **Node available on PATH** (the CLI bridge is a Node script).

## Run

```bash
# dry run — report per-table row counts, no writes
python scripts/catalyst/seed_datastore.py --via-cli .catalyst-build/appsail \
    --project-id 42171000000017001 --dry-run

# smoke test a couple of tables, capped
python scripts/catalyst/seed_datastore.py --via-cli .catalyst-build/appsail \
    --project-id 42171000000017001 --only State,District --limit 5

# full seed
python scripts/catalyst/seed_datastore.py --via-cli .catalyst-build/appsail \
    --project-id 42171000000017001
```

The full load is ~99k rows in ≤200-row chunks (~495 API calls, a few minutes).
Only per-table `load`/`skip` counts are printed — never any token.

## Expected row counts

| Table | Rows | | Table | Rows |
|---|--:|---|---|--:|
| State | 1 | | OccupationMaster | 8 |
| District | 12 | | CaseMaster | 16,652 |
| UnitType | 2 | | ComplainantDetails | 16,652 |
| Unit | 41 | | Victim | 13,263 |
| Rank | 2 | | Accused | 16,619 |
| Designation | 2 | | ActSectionAssociation | 24,509 |
| Employee | 58 | | ArrestSurrender | 6,743 |
| Court | 12 | | ChargesheetDetails | 4,233 |
| CrimeHead | 6 | | Act | 1 |
| CrimeSubHead | 30 | | Section | 39 |
| CaseCategory | 4 | | CrimeHeadActSection | 42 |
| GravityOffence | 2 | | ReligionMaster | 4 |
| CaseStatusMaster | 3 | | CasteMaster | 6 |
| | | | **Total** | **98,946** |

## Idempotency & re-runs (no primary keys)

The Data Store has **no user-defined primary keys** (documented PKs are ordinary
columns — see [datastore-type-mapping.md](datastore-type-mapping.md)), so re-run
safety cannot rely on PK-conflict. Instead the seed **skips any table that
already has rows**. This means:

- A failed/interrupted run is **resumable** — re-run it; loaded tables skip,
  unloaded ones fill in.
- Console edits are **never clobbered** by a re-run.
- **To force a reload:** clear the table in the Zoho console (Data Store →
  select table → delete rows), then re-run. The seed treats an empty table as
  loadable.

## Type coercion

Cells are coerced to each column's Data Store type (from `provision_datastore`'s
plan): `bigint`→int, `double`→float, `boolean`→true/false (from `1`/`0`),
`date`/`datetime`/`varchar`/`text`→string. A **blank cell is omitted**, leaving
the column null (sending `""` to a typed column is rejected by the API).

## Quota note (why Live only)

A dev-tier Catalyst project caps the Data Store at **5,000 rows/table**, below
`CaseMaster`'s 16,652. A `Live` project has production-tier quota. The seed
aborts on a non-`Live` project; `--allow-dev` overrides it only for a small
`--limit` smoke test.
