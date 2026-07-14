"""Dataset-agnostic ingestion pipeline (DATA-002/#15).

CSV per source table -> manifest validation (fail-fast on unknown columns) ->
FK integrity report -> idempotent load into the backing store through a
storage adapter. The dev-fixture SQLite adapter is implemented here; the
Catalyst Data Store adapter plugs into the same interface once CAT-002
provisioning is unblocked (RES-CATALYST-PROJECT-001) — no fake Catalyst
integration is present.

Raw values are preserved verbatim (no silent normalization); duplicates and
violations are rejected per-row and counted, never silently dropped.
"""

import csv
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

#: load order honouring FK direction (parents before children)
LOAD_ORDER = [
    "State", "District", "UnitType", "Unit", "Rank", "Designation", "Employee",
    "Court", "CrimeHead", "CrimeSubHead", "Act", "Section", "CrimeHeadActSection",
    "CaseCategory", "GravityOffence", "CaseStatusMaster", "ReligionMaster",
    "CasteMaster", "OccupationMaster", "CaseMaster", "ComplainantDetails",
    "Victim", "Accused", "ActSectionAssociation", "ArrestSurrender",
    "ChargesheetDetails",
]


@dataclass
class TableReport:
    loaded: int = 0
    rejected_duplicate_pk: int = 0
    rejected_bad_row: int = 0
    dangling_fks: dict[str, int] = field(default_factory=dict)
    null_rates: dict[str, float] = field(default_factory=dict)


@dataclass
class DataQualityReport:
    tables: dict[str, TableReport] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def total_loaded(self) -> int:
        return sum(t.loaded for t in self.tables.values())

    def to_json(self) -> str:
        return json.dumps(
            {
                "tables": {
                    k: {
                        "loaded": t.loaded,
                        "rejected_duplicate_pk": t.rejected_duplicate_pk,
                        "rejected_bad_row": t.rejected_bad_row,
                        "dangling_fks": t.dangling_fks,
                        "null_rates": t.null_rates,
                    }
                    for k, t in self.tables.items()
                },
                "errors": self.errors,
                "total_loaded": self.total_loaded,
            },
            indent=2,
        )


class IngestionError(ValueError):
    """Fail-fast structural error (unknown column, missing table file)."""


def _read_csv(path: Path, columns: list[str]) -> list[dict]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        unknown = set(header) - set(columns)
        if unknown:
            raise IngestionError(f"{path.name}: unknown columns {sorted(unknown)}")
        missing = set(columns) - set(header)
        if missing:
            raise IngestionError(f"{path.name}: missing columns {sorted(missing)}")
        return [{c: (None if row[c] == "" else row[c]) for c in columns} for row in reader]


def load_dataset(
    src_dir: str | Path,
    manifest_path: str | Path,
    conn: sqlite3.Connection,
) -> DataQualityReport:
    """Validate + load all source tables into the SQLite backing store.

    Idempotent by PK: re-running counts duplicates instead of double-loading.
    Tables without a documented PK (Q4) are replaced wholesale on re-run to
    stay idempotent (documented behaviour).
    """
    src = Path(src_dir)
    manifest = {
        k: v
        for k, v in json.loads(Path(manifest_path).read_text()).items()
        if not k.startswith("_")
    }
    report = DataQualityReport()

    tables_rows: dict[str, list[dict]] = {}
    for table in LOAD_ORDER:
        spec = manifest[table]
        path = src / f"{table}.csv"
        if not path.exists():
            raise IngestionError(f"missing table file: {path.name}")
        tables_rows[table] = _read_csv(path, spec["columns"])

    # FK integrity pass (string-normalized: Q3 value-join quirk)
    pk_values: dict[str, set[str]] = {
        t: {str(r[manifest[t]["pk"][0]]) for r in rows if r[manifest[t]["pk"][0]] is not None}
        for t, rows in tables_rows.items()
        if manifest[t]["pk"]
    }
    for table in LOAD_ORDER:
        spec = manifest[table]
        t_report = report.tables.setdefault(table, TableReport())
        for col, ref_table, ref_col in spec.get("fks", []):
            if ref_table not in pk_values or manifest[ref_table]["pk"] != [ref_col]:
                continue
            n = sum(
                1
                for r in tables_rows[table]
                if r.get(col) is not None and str(r[col]) not in pk_values[ref_table]
            )
            if n:
                t_report.dangling_fks[col] = n

    # load pass
    for table in LOAD_ORDER:
        spec = manifest[table]
        cols = spec["columns"]
        rows = tables_rows[table]
        t_report = report.tables[table]
        pk = spec["pk"]
        placeholders = ", ".join("?" * len(cols))
        col_list = ", ".join(cols)
        if not pk:
            conn.execute(f"DELETE FROM {table}")  # noqa: S608 — manifest-controlled name
        existing: set[str] = set()
        if pk:
            existing = {
                str(r[0])
                for r in conn.execute(f"SELECT {pk[0]} FROM {table}")  # noqa: S608
            }
        for r in rows:
            if pk:
                key = str(r[pk[0]])
                if key in existing:
                    t_report.rejected_duplicate_pk += 1
                    continue
                existing.add(key)
            try:
                conn.execute(
                    f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",  # noqa: S608
                    [r[c] for c in cols],
                )
                t_report.loaded += 1
            except sqlite3.Error as exc:
                t_report.rejected_bad_row += 1
                report.errors.append(f"{table}: {exc}")
        if rows:
            t_report.null_rates = {
                c: round(sum(1 for r in rows if r[c] is None) / len(rows), 4)
                for c in cols
                if any(r[c] is None for r in rows)
            }
    conn.commit()
    return report
