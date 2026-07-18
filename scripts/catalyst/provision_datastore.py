#!/usr/bin/env python3
"""Catalyst Data Store provisioning (CAT-002/#18).

Creates all source FIR tables (exact documented column names, from
docs/schema/schema-manifest.json) and the derived intelligence tables
(docs/schema/derived-intelligence-schema.md) in Catalyst Data Store.

Idempotent: create-if-missing; a second run is a no-op. Existing tables
with drifted columns are REPORTED and never silently altered (CAT-002
edge-case rule). Column-name fidelity is mandatory; type adaptation is
allowed and documented in docs/catalyst/datastore-type-mapping.md.

Usage:
    python scripts/catalyst/provision_datastore.py --dry-run   # offline plan
    python scripts/catalyst/provision_datastore.py             # provision
    python scripts/catalyst/provision_datastore.py --verify    # parity check

Environment (never committed — ADR-001):
    CATALYST_PROJECT_ID   Catalyst project id
    CATALYST_ORG_ID       Catalyst org id (CATALYST-ORG header)
    CATALYST_OAUTH_TOKEN  OAuth token with Data Store admin scope
    CATALYST_API_BASE     default https://api.catalyst.zoho.in
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "docs/schema/schema-manifest.json"
MATRIX_PATH = REPO_ROOT / "docs/schema/er-conformance-matrix.md"

#: Documented ER type → Catalyst Data Store type (adaptation table —
#: docs/catalyst/datastore-type-mapping.md; names/meaning never adapted).
TYPE_MAP = {
    "INT": "bigint",
    "BIT": "boolean",
    "DATE": "date",
    "DATETIME": "datetime",
    "DECIMAL": "double",
    "VARCHAR": "varchar",
    "CHAR": "varchar",
    "NVARCHAR(MAX)": "text",
}

#: Catalyst system columns present on every table — excluded from parity.
SYSTEM_COLUMNS = {"ROWID", "CREATORID", "CREATEDTIME", "MODIFIEDTIME"}

#: Derived intelligence tables (docs/schema/derived-intelligence-schema.md).
#: Only tables implemented by landed code are provisioned; engine result
#: tables (HotspotResult, TrendAlert, …) are added by their engine issues.
DERIVED_TABLES: dict[str, list[tuple[str, str]]] = {
    "IntelligenceRun": [
        ("run_id", "varchar"),
        ("intelligence_type", "varchar"),
        ("method_name", "varchar"),
        ("method_version", "varchar"),
        ("model_version", "varchar"),
        ("analysis_window_from", "datetime"),
        ("analysis_window_to", "datetime"),
        ("scope_district_id", "bigint"),
        ("scope_unit_id", "bigint"),
        ("status", "varchar"),
        ("error", "text"),
        ("generated_at", "datetime"),
        ("record_count", "bigint"),
    ],
    "IntelligenceEvidence": [
        ("evidence_id", "bigint"),
        ("run_id", "varchar"),
        ("result_ref", "varchar"),
        ("evidence_case_ids", "text"),
        ("factors", "text"),
        ("limitations", "text"),
        ("classification", "varchar"),
    ],
    "CrimeGraphNode": [
        ("node_id", "varchar"),
        ("node_type", "varchar"),
        ("entity_ref_id", "varchar"),
        ("label", "varchar"),
        ("run_id", "varchar"),
    ],
    "CrimeGraphEdge": [
        ("edge_id", "varchar"),
        ("source_node_id", "varchar"),
        ("target_node_id", "varchar"),
        ("relationship_type", "varchar"),
        ("weight", "double"),
        ("evidence_case_id", "bigint"),
        ("derivation", "varchar"),
        ("classification", "varchar"),
        ("run_id", "varchar"),
    ],
}


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    catalyst_type: str


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[ColumnSpec, ...]
    is_derived: bool


# -- documented schema -----------------------------------------------------
def parse_manifest(path: Path = MANIFEST_PATH) -> dict[str, dict]:
    manifest = json.loads(path.read_text())
    return {k: v for k, v in manifest.items() if not k.startswith("_")}


def parse_matrix_types(path: Path = MATRIX_PATH) -> dict[str, dict[str, str]]:
    """Column → documented ER type per table, from matrix §1 catalogue."""
    text = path.read_text()
    types: dict[str, dict[str, str]] = {}
    for section in re.split(r"\n### ", text)[1:]:
        m = re.match(r"1\.\d+ (\w+)", section)
        if not m:
            continue  # §2+ sections are not table catalogues
        table = m.group(1)
        cols: dict[str, str] = {}
        in_table = False
        for line in section.splitlines():
            if line.startswith("| Column | Type |"):
                in_table = True
                continue
            if in_table:
                if not line.startswith("|"):
                    break
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) >= 2 and cells[0] not in ("Column", "---", ""):
                    if set(cells[0]) != {"-"}:
                        cols[cells[0]] = cells[1]
        if cols:
            types[table] = cols
    return types


def build_plan(
    manifest: dict[str, dict] | None = None,
    matrix_types: dict[str, dict[str, str]] | None = None,
) -> list[TableSpec]:
    """Desired physical schema: all manifest source tables + derived tables.

    Referenced-but-undefined tables (matrix §2) are absent from the manifest
    and therefore never created.
    """
    manifest = manifest if manifest is not None else parse_manifest()
    matrix_types = matrix_types if matrix_types is not None else parse_matrix_types()
    plan: list[TableSpec] = []
    for table, spec in manifest.items():
        col_types = matrix_types.get(table, {})
        columns = []
        for col in spec["columns"]:
            er_type = col_types.get(col)
            if er_type is None:
                raise SystemExit(
                    f"matrix §1 documents no type for {table}.{col} — refusing to guess"
                )
            if er_type not in TYPE_MAP:
                raise SystemExit(f"unmapped ER type {er_type!r} for {table}.{col}")
            columns.append(ColumnSpec(col, TYPE_MAP[er_type]))
        plan.append(TableSpec(table, tuple(columns), is_derived=False))
    for table, cols in DERIVED_TABLES.items():
        plan.append(
            TableSpec(table, tuple(ColumnSpec(n, t) for n, t in cols), is_derived=True)
        )
    return plan


# -- diff / parity -----------------------------------------------------------
def diff_plan(
    plan: list[TableSpec], existing: dict[str, list[str]]
) -> tuple[list[TableSpec], list[str], dict[str, dict[str, list[str]]]]:
    """Split plan into (to_create, in_parity, drift-report).

    Drift = existing table whose physical columns != documented columns
    (system columns ignored). Drift is reported, NEVER altered here.
    """
    to_create: list[TableSpec] = []
    ok: list[str] = []
    drift: dict[str, dict[str, list[str]]] = {}
    for spec in plan:
        if spec.name not in existing:
            to_create.append(spec)
            continue
        physical = [c for c in existing[spec.name] if c.upper() not in SYSTEM_COLUMNS]
        want = [c.name for c in spec.columns]
        missing = [c for c in want if c not in physical]
        unexpected = [c for c in physical if c not in want]
        if missing or unexpected:
            drift[spec.name] = {"missing": missing, "unexpected": unexpected}
        else:
            ok.append(spec.name)
    return to_create, ok, drift


# -- Catalyst REST client ----------------------------------------------------
class CatalystClient:
    """Thin Data Store admin client (table list/create) over urllib."""

    def __init__(self) -> None:
        self.base = os.environ.get("CATALYST_API_BASE", "https://api.catalyst.zoho.in")
        self.project_id = os.environ.get("CATALYST_PROJECT_ID")
        self.org_id = os.environ.get("CATALYST_ORG_ID")
        self.token = os.environ.get("CATALYST_OAUTH_TOKEN")
        missing = [
            k
            for k, v in {
                "CATALYST_PROJECT_ID": self.project_id,
                "CATALYST_ORG_ID": self.org_id,
                "CATALYST_OAUTH_TOKEN": self.token,
            }.items()
            if not v
        ]
        if missing:
            raise SystemExit(
                "missing environment: " + ", ".join(missing) + " (see module docstring); "
                "use --dry-run for the offline plan"
            )

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        req = urllib.request.Request(
            f"{self.base}/baas/v1/project/{self.project_id}{path}",
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": f"Zoho-oauthtoken {self.token}",
                "CATALYST-ORG": str(self.org_id),
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req) as resp:  # noqa: S310 — https API host
            return json.loads(resp.read().decode())

    def list_tables(self) -> dict[str, list[str]]:
        """Existing table → physical column names."""
        data = self._request("GET", "/table").get("data", [])
        out: dict[str, list[str]] = {}
        for t in data:
            cols = self._request("GET", f"/table/{t['table_id']}/column").get("data", [])
            out[t["table_name"]] = [c["column_name"] for c in cols]
        return out

    def create_table(self, spec: TableSpec) -> None:
        self._request(
            "POST",
            "/table",
            {
                "table_name": spec.name,
                "column_details": [
                    {"column_name": c.name, "data_type": c.catalyst_type}
                    for c in spec.columns
                ],
            },
        )


# -- CLI ----------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="print the plan; no API calls")
    ap.add_argument("--verify", action="store_true", help="parity check only; create nothing")
    args = ap.parse_args(argv)

    plan = build_plan()
    src = sum(1 for t in plan if not t.is_derived)
    drv = len(plan) - src
    print(f"plan: {src} source tables + {drv} derived tables")

    if args.dry_run:
        for spec in plan:
            kind = "DERIVED" if spec.is_derived else "SOURCE"
            print(f"  [{kind}] {spec.name}: "
                  + ", ".join(f"{c.name}:{c.catalyst_type}" for c in spec.columns))
        return 0

    client = CatalystClient()
    existing = client.list_tables()
    to_create, ok, drift = diff_plan(plan, existing)

    for table, d in drift.items():
        print(f"DRIFT {table}: missing={d['missing']} unexpected={d['unexpected']}"
              " — refusing to alter; reconcile manually", file=sys.stderr)

    if args.verify:
        print(f"parity: {len(ok)} ok, {len(to_create)} absent, {len(drift)} drifted")
        return 1 if (drift or to_create) else 0

    for spec in to_create:
        print(f"creating {spec.name} ({len(spec.columns)} columns)")
        client.create_table(spec)
    print(f"done: created {len(to_create)}, unchanged {len(ok)}, drift {len(drift)}")
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
