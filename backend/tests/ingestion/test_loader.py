"""DATA-002 (#15): ingestion validation, idempotency, DQ report (dev fixture)."""

import json
from pathlib import Path

import pytest

from kavach.datagen.generator import generate_dataset
from kavach.ingestion.loader import IngestionError, load_dataset
from kavach.repositories.case_repository import CaseRepository
from kavach.repositories.dev_fixture import connect

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"


@pytest.fixture(scope="module")
def dataset_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("ingest-src")
    generate_dataset(out, MANIFEST, seed=99, background_cases=300)
    return out


def test_full_load_with_dq_report(dataset_dir):
    conn = connect()
    report = load_dataset(dataset_dir, MANIFEST, conn)
    n_cases = conn.execute("SELECT COUNT(*) FROM CaseMaster").fetchone()[0]
    assert n_cases == report.tables["CaseMaster"].loaded > 300
    # designed dangling CourtIDs surface in the report
    assert report.tables["CaseMaster"].dangling_fks.get("CourtID") == 5
    # null rates reported for nullable columns (missing coordinates)
    assert report.tables["CaseMaster"].null_rates.get("latitude", 0) > 0
    # loaded rows readable through the repository layer (raw in == raw out)
    first_id = conn.execute("SELECT MIN(CaseMasterID) FROM CaseMaster").fetchone()[0]
    case = CaseRepository(conn).get_case(int(first_id))
    assert case is not None and case.case_master_id == int(first_id)


def test_rerun_is_idempotent(dataset_dir):
    conn = connect()
    r1 = load_dataset(dataset_dir, MANIFEST, conn)
    r2 = load_dataset(dataset_dir, MANIFEST, conn)
    n_cases = conn.execute("SELECT COUNT(*) FROM CaseMaster").fetchone()[0]
    assert n_cases == r1.tables["CaseMaster"].loaded
    assert r2.tables["CaseMaster"].loaded == 0
    assert r2.tables["CaseMaster"].rejected_duplicate_pk == r1.tables["CaseMaster"].loaded
    # PK-less tables (Q4) replaced wholesale, not duplicated
    n_assoc = conn.execute("SELECT COUNT(*) FROM ActSectionAssociation").fetchone()[0]
    assert n_assoc == r2.tables["ActSectionAssociation"].loaded


def test_unknown_column_fails_fast(dataset_dir, tmp_path):
    corrupted = tmp_path / "bad"
    corrupted.mkdir()
    for f in Path(dataset_dir).glob("*.csv"):
        (corrupted / f.name).write_text(f.read_text())
    cm = corrupted / "CaseMaster.csv"
    lines = cm.read_text().splitlines()
    lines[0] += ",InventedColumn"
    lines[1] += ",x"
    cm.write_text("\n".join(lines) + "\n")
    with pytest.raises(IngestionError, match="InventedColumn"):
        load_dataset(corrupted, MANIFEST, connect())


def test_missing_table_file_fails_fast(dataset_dir, tmp_path):
    partial = tmp_path / "partial"
    partial.mkdir()
    for f in Path(dataset_dir).glob("*.csv"):
        if f.name != "Victim.csv":
            (partial / f.name).write_text(f.read_text())
    with pytest.raises(IngestionError, match="Victim"):
        load_dataset(partial, MANIFEST, connect())


def test_duplicate_pk_rejected_and_counted(dataset_dir, tmp_path):
    dup = tmp_path / "dup"
    dup.mkdir()
    for f in Path(dataset_dir).glob("*.csv"):
        (dup / f.name).write_text(f.read_text())
    cm = dup / "CaseMaster.csv"
    lines = cm.read_text().splitlines()
    cm.write_text("\n".join(lines + [lines[1]]) + "\n")  # duplicate first case
    report = load_dataset(dup, MANIFEST, connect())
    assert report.tables["CaseMaster"].rejected_duplicate_pk == 1


def test_report_serializes_to_json(dataset_dir):
    report = load_dataset(dataset_dir, MANIFEST, connect())
    parsed = json.loads(report.to_json())
    assert parsed["total_loaded"] == report.total_loaded
    assert "CaseMaster" in parsed["tables"]
