#!/usr/bin/env python3
"""Bulk-load the enriched synthetic CSVs into the Catalyst Data Store (CAT/#…).

Local, one-shot operator tool — NOT part of the AppSail runtime. It reads every
source CSV from ``data/synthetic`` and inserts the rows into the matching Data
Store table, in FK-dependency order (parents before children), so the console
becomes the live source of truth the app can later read from (PR-B).

Safety properties (the two things that matter for a live DB):
  * NO DUPLICATES — the seed is idempotent by SKIPPING any table that already
    has rows (GET .../row → non-empty). The Data Store has no user-defined
    primary keys, so this row-count guard is the re-run safety net: a
    half-finished run resumes, and console edits are never clobbered. To force a
    reload, clear the table in the Zoho console first.
  * NO SCHEMA ERRORS MID-LOAD — every value is coerced and validated against the
    LIVE column types (and varchar lengths) in a pre-flight pass BEFORE any row
    is written. If a single cell fails, the whole run aborts with a report and
    writes nothing, so a type mismatch can never leave a table half-loaded.

Other constraints:
  * Row-insert API is ``POST /table/{table_id}/row`` with a JSON *array* body,
    max 200 rows/call — rows are chunked, through the same authenticated
    transport + retry/backoff as provision_datastore.py.
  * Dev-tier projects cap the Data Store at 5,000 rows/table (< our 16,652
    cases), so the seed refuses a non-``Live`` project unless --allow-dev.
  * No secrets are printed — only per-table loaded/skipped counts.

Usage (developer VM, already ``catalyst login``-ed):
    python scripts/catalyst/seed_datastore.py --via-cli .catalyst-build/appsail \
        --project-id 42171000000017001
    python scripts/catalyst/seed_datastore.py --via-cli <app-dir> --dry-run
    python scripts/catalyst/seed_datastore.py --via-cli <app-dir> \
        --only State,District --limit 5      # smoke test a couple of tables

Environment (token path, e.g. CI — never committed, ADR-001):
    CATALYST_PROJECT_ID / CATALYST_ORG_ID / CATALYST_OAUTH_TOKEN
    KAVACH_DATA_DIR   override the CSV directory (default data/synthetic)
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent

# Reuse provision_datastore.py's authenticated transports and the ingestion
# loader's canonical FK-ordered table list, rather than re-deriving them.
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT / "backend"))
from provision_datastore import (  # noqa: E402
    CatalystClient,
    CliSessionClient,
    DataStoreAdmin,
)
from kavach.ingestion.loader import LOAD_ORDER  # noqa: E402

#: Data Store row-insert cap (verified against the live API).
CHUNK_SIZE = 200

#: Catalyst system columns — present on every table, never sent on insert.
SYSTEM_COLUMNS = {"ROWID", "CREATORID", "CREATEDTIME", "MODIFIEDTIME"}

#: CSV tokens meaning boolean true / false (Active flags, BIT columns).
_TRUE = {"1", "true", "t", "yes", "y"}
_FALSE = {"0", "false", "f", "no", "n"}

#: Cap on example bad values reported per column, to keep the report readable.
_MAX_SAMPLES = 5


def data_dir() -> Path:
    """Directory holding the generated CSVs (override with KAVACH_DATA_DIR)."""
    return Path(os.environ.get("KAVACH_DATA_DIR", REPO_ROOT / "data" / "synthetic"))


def _coerce(value: str, ctype: str) -> object:
    """Coerce a raw non-empty CSV string to the type the column expects.

    Raises ValueError if the value does not fit the column type — the caller
    turns that into a pre-flight problem, never a mid-load API rejection.
    """
    if ctype == "bigint":
        return int(value)
    if ctype == "double":
        return float(value)
    if ctype == "boolean":
        low = value.strip().lower()
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
        raise ValueError(f"unparseable boolean {value!r}")
    # date / datetime / varchar / text — the API parses the string forms the
    # generator emits ("2023-07-07", "2023-07-06 13:31:00").
    return value


def live_catalogue(client: DataStoreAdmin) -> tuple[dict[str, str], str]:
    """(table_name → table_id, project_type) straight from the live API."""
    data = client._request("GET", "/table").get("data", [])
    if not data:
        raise SystemExit("the Data Store has no tables — run provision_datastore.py first")
    names = {t["table_name"]: t["table_id"] for t in data}
    project_type = data[0].get("project_id", {}).get("project_type", "unknown")
    return names, project_type


def live_columns(client: DataStoreAdmin, table_id: str) -> dict[str, dict]:
    """column_name → {"type": data_type, "max_length": int|None} (live schema)."""
    cols = client._request("GET", f"/table/{table_id}/column").get("data", [])
    out: dict[str, dict] = {}
    for c in cols:
        if c["column_name"] in SYSTEM_COLUMNS:
            continue
        ml = c.get("max_length")
        out[c["column_name"]] = {
            "type": c["data_type"],
            "max_length": int(ml) if ml not in (None, "") else None,
        }
    return out


def prepare_table(
    table: str, cols: dict[str, dict], limit: int | None
) -> tuple[list[dict], list[str]]:
    """Read a CSV and coerce every cell against the live column types.

    Returns (rows_ready_to_insert, problems). A blank cell is omitted so the
    column stays null. Any coercion failure or varchar-overflow is collected as
    a problem string rather than raised, so the pre-flight can report the FULL
    picture across all tables before deciding to abort.
    """
    path = data_dir() / f"{table}.csv"
    if not path.exists():
        return [], [f"{table}: missing CSV {path}"]
    rows: list[dict] = []
    problems: list[str] = []
    samples: dict[str, list[str]] = {}

    def note(col: str, msg: str, sample: str) -> None:
        bucket = samples.setdefault(f"{table}.{col} {msg}", [])
        if len(bucket) < _MAX_SAMPLES and sample not in bucket:
            bucket.append(sample)

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        unknown = set(reader.fieldnames or []) - set(cols) - SYSTEM_COLUMNS
        if unknown:
            problems.append(f"{table}: CSV columns absent from live schema: {sorted(unknown)}")
        for raw in reader:
            row: dict = {}
            for col, meta in cols.items():
                value = raw.get(col, "")
                if value == "":
                    continue
                ctype = meta["type"]
                try:
                    coerced = _coerce(value, ctype)
                except ValueError:
                    note(col, f"cannot coerce to {ctype}", value)
                    continue
                if ctype == "varchar" and meta["max_length"] and len(value) > meta["max_length"]:
                    note(col, f"exceeds varchar({meta['max_length']})", value)
                    continue
                row[col] = coerced
            rows.append(row)
            if limit is not None and len(rows) >= limit:
                break
    for label, examples in samples.items():
        problems.append(f"{label} — e.g. {examples}")
    return rows, problems


def _chunks(rows: list[dict], size: int):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def table_is_empty(client: DataStoreAdmin, table_id: str) -> bool:
    """True if the table currently has no rows (idempotency / no-dup guard)."""
    data = client._request("GET", f"/table/{table_id}/row").get("data", [])
    return not data


def insert_rows(client: DataStoreAdmin, table_id: str, rows: list[dict]) -> int:
    """Insert rows in ≤200-row chunks; returns the number sent."""
    total = 0
    for chunk in _chunks(rows, CHUNK_SIZE):
        client._request("POST", f"/table/{table_id}/row", chunk)
        total += len(chunk)
        print(f"    +{total}/{len(rows)}", end="\r", file=sys.stderr, flush=True)
    if rows:
        print(" " * 40, end="\r", file=sys.stderr)  # clear progress line
    return total


def seed(
    client: DataStoreAdmin,
    *,
    only: list[str] | None,
    limit: int | None,
    allow_dev: bool,
    dry_run: bool,
) -> int:
    names, project_type = live_catalogue(client)
    print(f"project_type={project_type}; {len(names)} tables in the Data Store")

    if project_type != "Live" and not allow_dev:
        raise SystemExit(
            f"refusing to seed a {project_type!r} project — dev-tier Data Store is "
            "capped at 5,000 rows/table, below our dataset. Point at the Live "
            "project, or pass --allow-dev with a small --limit for a smoke test."
        )

    if only:
        unknown = [t for t in only if t not in LOAD_ORDER]
        if unknown:
            raise SystemExit(f"--only names unknown tables: {unknown}")
    order = [t for t in LOAD_ORDER if (only is None or t in only)]

    missing = [t for t in order if t not in names]
    if missing:
        raise SystemExit(f"tables not provisioned (run provision_datastore.py first): {missing}")

    # -- decide skip vs load (no duplicates) ---------------------------------
    to_load: list[str] = []
    skipped = 0
    for table in order:
        if dry_run:
            to_load.append(table)
        elif table_is_empty(client, names[table]):
            to_load.append(table)
        else:
            print(f"  skip {table} (already populated)")
            skipped += 1

    # -- pre-flight: coerce + validate EVERYTHING before writing anything ----
    prepared: dict[str, list[dict]] = {}
    problems: list[str] = []
    for table in to_load:
        rows, probs = prepare_table(table, live_columns(client, names[table]), limit)
        prepared[table] = rows
        problems.extend(probs)
    if problems:
        print("\nPRE-FLIGHT FAILED — nothing was written. Fix these first:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(1)

    if dry_run:
        for table in to_load:
            print(f"  [dry-run] {table}: would load {len(prepared[table])} rows (validated)")
        print(f"done: validated {sum(len(r) for r in prepared.values())} rows, {skipped} skipped")
        return 0

    # -- load (pre-flight passed) --------------------------------------------
    loaded_total = 0
    for table in to_load:
        n = insert_rows(client, names[table], prepared[table])
        print(f"  load {table}: {n} rows")
        loaded_total += n

    print(f"done: loaded {loaded_total} rows across {len(to_load)} tables, {skipped} skipped")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--via-cli",
        metavar="APP_DIR",
        help="authenticate through the logged-in Catalyst CLI session (APP_DIR "
        "contains catalyst.json) instead of CATALYST_OAUTH_TOKEN",
    )
    ap.add_argument(
        "--project-id",
        default=os.environ.get("CATALYST_PROJECT_ID"),
        help="Catalyst project id (defaults to $CATALYST_PROJECT_ID); required with --via-cli",
    )
    ap.add_argument("--only", help="comma-separated subset of tables to load")
    ap.add_argument("--limit", type=int, help="load at most N rows per table (smoke test)")
    ap.add_argument(
        "--allow-dev",
        action="store_true",
        help="permit seeding a non-Live project (only sensible with a small --limit)",
    )
    ap.add_argument("--dry-run", action="store_true", help="validate + report counts; no API writes")
    args = ap.parse_args(argv)

    client: DataStoreAdmin
    if args.via_cli:
        if not args.project_id:
            raise SystemExit("--via-cli requires --project-id (or $CATALYST_PROJECT_ID)")
        client = CliSessionClient(args.project_id, args.via_cli)
    else:
        client = CatalystClient()

    only = [t.strip() for t in args.only.split(",")] if args.only else None
    return seed(
        client,
        only=only,
        limit=args.limit,
        allow_dev=args.allow_dev,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
