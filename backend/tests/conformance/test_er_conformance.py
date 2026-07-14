"""ER-007 (#12): executable ER Schema Conformance Gate.

Sources of truth: docs/schema/schema-manifest.json (machine-readable, generated
from the conformance matrix and diff-reviewed) vs. the actual implementation:
dev-fixture DDL, repository column maps, domain entities, generated dataset.

Any drift — renamed column, invented field, missing table — fails CI naming
the exact table/column.
"""

import json
import re
from pathlib import Path

from kavach.datagen.generator import DatasetGenerator
from kavach.repositories import (
    arrest_repository,
    case_repository,
    classification_repository,
    organization_repository,
    person_repository,
)
from kavach.repositories.dev_fixture import connect

BACKEND = Path(__file__).resolve().parents[2]
ROOT = BACKEND.parent
MANIFEST = json.loads((ROOT / "docs/schema/schema-manifest.json").read_text())
TABLES = {k: v for k, v in MANIFEST.items() if k != "_meta"}

#: repository column maps (DB column -> domain field), the app-side truth
REPO_MAPS: dict[str, dict[str, str]] = {
    "CaseMaster": case_repository._CASE_COLS,
    "ActSectionAssociation": case_repository._ASSOC_COLS,
    "ChargesheetDetails": case_repository._CS_COLS,
    "Accused": person_repository._ACCUSED_COLS,
    "Victim": person_repository._VICTIM_COLS,
    "ComplainantDetails": person_repository._COMPLAINANT_COLS,
    "ArrestSurrender": arrest_repository._COLS,
    **classification_repository._TABLES,
    **organization_repository._TABLES,
}


def test_manifest_covers_all_26_documented_tables():
    assert len(TABLES) == 26, sorted(TABLES)
    # referenced-but-undefined tables intentionally absent (matrix §2)
    assert "Inv_OccuranceTime" not in TABLES
    assert "inv_arrestsurrenderaccused" not in TABLES


def test_dev_fixture_ddl_matches_manifest_exactly():
    conn = connect()
    for table, spec in TABLES.items():
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        assert cols == set(spec["columns"]), f"{table}: DDL drift {cols ^ set(spec['columns'])}"


def test_repository_maps_match_manifest_exactly():
    assert set(REPO_MAPS) == set(TABLES), set(REPO_MAPS) ^ set(TABLES)
    for table, mapping in REPO_MAPS.items():
        assert set(mapping) == set(TABLES[table]["columns"]), (
            f"{table}: repository map drift {set(mapping) ^ set(TABLES[table]['columns'])}"
        )


def test_manifest_pks_present_in_columns():
    for table, spec in TABLES.items():
        for pk in spec["pk"]:
            assert pk in spec["columns"], f"{table}: PK {pk} not a column"


def _generated() -> tuple[dict, dict]:
    gen = DatasetGenerator(seed=1, background_cases=400)  # small = fast CI
    gen.generate()
    return gen.tables, gen.ground_truth


def test_fk_integrity_of_generated_dataset():
    """Every FK value in the synthetic dataset resolves, except the designed
    data-quality danglings (5 CourtID references, DATA-001)."""
    tables, gt = _generated()
    # string-normalized PK sets: FK joins compare by value, honouring the
    # documented Q3 INT-vs-VARCHAR quirk (ActID int -> ActCode "1")
    ids = {t: {str(r[TABLES[t]["pk"][0]]) for r in rows}
           for t, rows in tables.items() if TABLES[t]["pk"]}
    dangling: dict[str, int] = {}
    for table, spec in TABLES.items():
        for col, ref_table, ref_col in spec.get("fks", []):
            if ref_table not in ids or TABLES[ref_table]["pk"] != [ref_col]:
                continue  # composite-key FKs (Section Q4) checked below
            for row in tables.get(table, []):
                v = row.get(col)
                if v is not None and str(v) not in ids[ref_table]:
                    dangling[f"{table}.{col}"] = dangling.get(f"{table}.{col}", 0) + 1
    designed = len(gt["dangling_court_case_ids"])
    assert dangling.pop("CaseMaster.CourtID", 0) == designed
    assert dangling == {}, f"unexpected dangling FKs: {dangling}"


def test_q3_value_joins_resolve_in_generated_dataset():
    tables, _ = _generated()
    acts = {r["ActCode"] for r in tables["Act"]}
    sections = {(r["ActCode"], r["SectionCode"]) for r in tables["Section"]}
    for row in tables["ActSectionAssociation"]:
        assert str(row["ActID"]) in acts
        assert (str(row["ActID"]), str(row["SectionID"])) in sections


# ---------------------------------------------------------------------------
# Semantic guards (ADR-003 / ADR-009 / ADR-011)
# ---------------------------------------------------------------------------

def _kavach_sources(exclude: tuple[str, ...] = ()) -> list[Path]:
    return [p for p in (BACKEND / "kavach").rglob("*.py")
            if "__pycache__" not in p.parts and not set(exclude) & set(p.parts)]


def test_engines_cannot_reach_ground_truth():
    """ADR-011: no module outside datagen imports datagen or reads
    ground_truth.json — engines must discover patterns, never read answers."""
    offenders = []
    for p in _kavach_sources(exclude=("datagen",)):
        src = p.read_text()
        if re.search(r"from kavach\.datagen|import kavach\.datagen|ground_truth", src):
            offenders.append(str(p.relative_to(BACKEND)))
    assert offenders == [], offenders


def test_no_cross_case_personid_join_anywhere():
    """ADR-003: PersonID never appears in JOIN/WHERE/GROUP BY SQL contexts."""
    pattern = re.compile(r"(JOIN[^\n]*PersonID|WHERE[^\n]*PersonID|GROUP BY[^\n]*PersonID)")
    offenders = [str(p.relative_to(BACKEND)) for p in _kavach_sources()
                 if pattern.search(p.read_text())]
    assert offenders == [], offenders


def test_no_protected_demographics_in_analytics():
    """ADR-009: complainant demographic fields never referenced by engines."""
    prohibited = re.compile(r"religion_id|caste_id|occupation_id|ReligionID|CasteID|OccupationID")
    offenders = []
    for p in (BACKEND / "kavach/analytics").rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        if prohibited.search(p.read_text()):
            offenders.append(str(p.relative_to(BACKEND)))
    assert offenders == [], offenders


def test_mutation_check_guards_actually_fire():
    """Self-test: a synthetic violation is caught by each guard pattern."""
    assert re.search(r"WHERE[^\n]*PersonID", "SELECT 1 WHERE a.PersonID = b.PersonID")
    assert re.search(r"from kavach\.datagen|ground_truth",
                     "from kavach.datagen import config")
