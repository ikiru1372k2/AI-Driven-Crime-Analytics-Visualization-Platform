"""CAT-002/#18: provisioning plan parity + idempotency semantics.

These tests exercise the offline plan/diff logic. The live smoke insert
against a real Data Store requires Catalyst credentials
(RES-CATALYST-PROJECT-001) and runs manually via --verify.
"""

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/catalyst/provision_datastore.py"

spec = importlib.util.spec_from_file_location("provision_datastore", SCRIPT)
prov = importlib.util.module_from_spec(spec)
sys.modules["provision_datastore"] = prov
spec.loader.exec_module(prov)


@pytest.fixture(scope="module")
def plan():
    return prov.build_plan()


def test_plan_covers_manifest_exactly(plan):
    manifest = prov.parse_manifest()
    source = {t.name for t in plan if not t.is_derived}
    assert source == set(manifest)  # all 26, nothing extra
    # referenced-but-undefined tables (matrix §2) are never created
    assert "Inv_OccuranceTime" not in source
    assert "inv_arrestsurrenderaccused" not in source


def test_column_name_fidelity(plan):
    """Physical column names == documented names, order preserved."""
    manifest = prov.parse_manifest()
    for spec_ in plan:
        if spec_.is_derived:
            continue
        assert [c.name for c in spec_.columns] == manifest[spec_.name]["columns"]
    by_name = {t.name: t for t in plan}
    cols = {c.name for c in by_name["CasteMaster"].columns}
    assert "caste_master_id" in cols  # snake_case fidelity
    assert {"latitude", "longitude", "BriefFacts"} <= {
        c.name for c in by_name["CaseMaster"].columns
    }
    assert "csdate" in {c.name for c in by_name["ChargesheetDetails"].columns}


def test_every_column_has_documented_type_mapping(plan):
    for spec_ in plan:
        for col in spec_.columns:
            assert col.catalyst_type in {
                "bigint", "boolean", "date", "datetime", "double", "varchar", "text"
            }, f"{spec_.name}.{col.name} -> {col.catalyst_type}"


def test_documented_type_adaptations(plan):
    by_name = {t.name: {c.name: c.catalyst_type for c in t.columns} for t in plan}
    case = by_name["CaseMaster"]
    assert case["IncidentFromDate"] == "datetime"
    assert case["latitude"] == "double"
    assert case["BriefFacts"] == "text"  # NVARCHAR(MAX)
    assert case["CaseMasterID"] == "bigint"
    assert by_name["Act"]["Active"] == "boolean"  # BIT
    assert by_name["Victim"]["VictimPolice"] == "varchar"  # Q2: documented VARCHAR


def test_derived_tables_present_with_provenance_columns(plan):
    by_name = {t.name: t for t in plan}
    for table in ("IntelligenceRun", "IntelligenceEvidence", "CrimeGraphNode", "CrimeGraphEdge"):
        assert by_name[table].is_derived
    edge_cols = {c.name for c in by_name["CrimeGraphEdge"].columns}
    assert {"evidence_case_id", "derivation", "classification", "run_id"} <= edge_cols
    assert {"classification", "run_id"} <= {
        c.name for c in by_name["IntelligenceEvidence"].columns
    }


def test_derived_matches_dev_fixture_ddl(plan):
    """The provisioned derived schema equals what the code actually writes."""
    from kavach.graph.repository import GraphRepository
    from kavach.provenance import ProvenanceRepository
    from kavach.repositories.dev_fixture import connect

    conn = connect()
    ProvenanceRepository(conn)
    GraphRepository(conn)
    by_name = {t.name: t for t in plan}
    for table in ("IntelligenceRun", "IntelligenceEvidence", "CrimeGraphNode", "CrimeGraphEdge"):
        physical = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        assert [c.name for c in by_name[table].columns] == physical, table


def test_diff_create_if_missing_and_second_run_noop(plan):
    # clean project: everything is created
    to_create, ok, drift = prov.diff_plan(plan, existing={})
    assert len(to_create) == len(plan) and not ok and not drift
    # after provisioning (system columns present): full parity, no-op
    existing = {
        t.name: ["ROWID", "CREATORID", "CREATEDTIME", "MODIFIEDTIME"]
        + [c.name for c in t.columns]
        for t in plan
    }
    to_create, ok, drift = prov.diff_plan(plan, existing)
    assert not to_create and not drift and len(ok) == len(plan)


def test_drifted_table_reported_never_altered(plan):
    existing = {
        "CaseMaster": ["ROWID", "CaseMasterID", "CrimeNo", "RenamedColumn"],
    }
    to_create, ok, drift = prov.diff_plan(plan, existing)
    assert "CaseMaster" not in [t.name for t in to_create]
    assert "CaseMaster" not in ok
    assert "RenamedColumn" in drift["CaseMaster"]["unexpected"]
    assert "latitude" in drift["CaseMaster"]["missing"]


def test_matrix_types_cover_all_manifest_columns():
    manifest = prov.parse_manifest()
    types = prov.parse_matrix_types()
    for table, spec_ in manifest.items():
        for col in spec_["columns"]:
            assert col in types.get(table, {}), f"matrix §1 lacks type for {table}.{col}"


def test_smoke_insert_against_provisioned_shape():
    """CaseMaster smoke: the provisioned column set accepts a repository row.

    Runs against the dev-fixture backend (same documented columns); the
    identical insert against live Data Store is the manual --verify smoke.
    """
    from datetime import datetime

    from kavach.domain.case import CaseMaster
    from kavach.repositories.case_repository import CaseRepository
    from kavach.repositories.dev_fixture import connect

    plan_cols = {
        c.name for t in prov.build_plan() if t.name == "CaseMaster" for c in t.columns
    }
    conn = connect()
    fixture_cols = {r[1] for r in conn.execute("PRAGMA table_info(CaseMaster)")}
    assert plan_cols == fixture_cols
    repo = CaseRepository(conn)
    repo.insert_case(
        CaseMaster(
            case_master_id=1,
            crime_no="10441000120250000 1",
            crime_registered_date=datetime(2025, 1, 1),
        )
    )
    assert repo.get_case(1) is not None


def test_dry_run_needs_no_credentials(plan, capsys, monkeypatch):
    for var in ("CATALYST_PROJECT_ID", "CATALYST_ORG_ID", "CATALYST_OAUTH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    assert prov.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "26 source tables + 4 derived tables" in out


def _sqlite_existing(conn: sqlite3.Connection) -> dict[str, list[str]]:
    tables = [
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    ]
    return {t: [r[1] for r in conn.execute(f"PRAGMA table_info({t})")] for t in tables}


def test_full_parity_against_dev_fixture(plan):
    """ER gate cross-check: dev fixture physical schema == provisioning plan
    for every table both sides define."""
    from kavach.graph.repository import GraphRepository
    from kavach.provenance import ProvenanceRepository
    from kavach.repositories.dev_fixture import connect

    conn = connect()
    ProvenanceRepository(conn)
    GraphRepository(conn)
    to_create, ok, drift = prov.diff_plan(plan, _sqlite_existing(conn))
    assert not drift, drift
