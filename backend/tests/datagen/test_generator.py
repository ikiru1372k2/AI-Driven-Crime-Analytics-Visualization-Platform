"""DATA-001 (#14): determinism, manifest conformance, ground-truth presence."""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from kavach.datagen import config as cfg
from kavach.datagen.generator import generate_dataset

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    out = tmp_path_factory.mktemp("synth")
    gen = generate_dataset(out, MANIFEST, seed=20260714, background_cases=600)
    return out, gen


def _rows(out: Path, table: str) -> list[dict]:
    with (out / f"{table}.csv").open() as f:
        return list(csv.DictReader(f))


def test_determinism_same_seed_identical_bytes(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generate_dataset(a, MANIFEST, seed=42, background_cases=200)
    generate_dataset(b, MANIFEST, seed=42, background_cases=200)
    for f in sorted(a.iterdir()):
        assert f.read_bytes() == (b / f.name).read_bytes(), f.name


def test_all_manifest_tables_written_with_exact_columns(dataset):
    out, _ = dataset
    manifest = json.loads(MANIFEST.read_text())
    for table, spec in manifest.items():
        if table.startswith("_"):
            continue
        path = out / f"{table}.csv"
        assert path.exists(), table
        with path.open() as f:
            header = next(csv.reader(f))
        assert header == spec["columns"], f"{table} header drift"


def test_synthetic_marker_and_ground_truth_present(dataset):
    out, _ = dataset
    assert "SYNTHETIC" in (out / "_SYNTHETIC_DATA_MARKER.txt").read_text()
    gt = json.loads((out / "ground_truth.json").read_text())
    assert {"hotspot", "mo_pattern", "trend_spike", "identity_fragment",
            "same_name_control", "anomaly_case", "data_quality"} <= set(gt)


def test_hotspot_cluster_statistically_present(dataset):
    out, gen = dataset
    gt = gen.ground_truth["hotspot"]
    cases = {r["CaseMasterID"]: r for r in _rows(out, "CaseMaster")}
    inside = 0
    for cid in gt["case_ids"]:
        r = cases[str(cid)]
        lat, lon = float(r["latitude"]), float(r["longitude"])
        # crude metres approximation adequate at this radius
        dlat = (lat - gt["center_lat"]) * 111_320
        dlon = (lon - gt["center_lon"]) * 96_000
        hour = datetime.fromisoformat(r["IncidentFromDate"]).hour
        in_window = hour >= gt["hours"][0] or hour <= gt["hours"][1]
        if (dlat**2 + dlon**2) ** 0.5 <= gt["radius_m"] * 1.1 and in_window:
            inside += 1
    assert inside >= 0.95 * len(gt["case_ids"])
    assert len(gt["case_ids"]) == cfg.HOTSPOT["case_count"]


def test_trend_spike_exceeds_baseline(dataset):
    out, gen = dataset
    sp = gen.ground_truth["trend_spike"]
    cases = _rows(out, "CaseMaster")
    window_from = datetime.fromisoformat(sp["window_from"])
    current = sum(
        1 for r in cases
        if r["PoliceStationID"] == str(sp["unit_id"])
        and r["CrimeMinorHeadID"] == str(sp["sub_head_id"])
        and r["IncidentFromDate"] and datetime.fromisoformat(r["IncidentFromDate"]) >= window_from
    )
    weekly_now = current / (sp["spike_days"] / 7)
    assert weekly_now >= 2 * sp["baseline_weekly_mean"]


def test_mo_pattern_narratives_contain_signals(dataset):
    out, gen = dataset
    ids = {str(i) for i in gen.ground_truth["mo_pattern"]["case_ids"]}
    assert len(ids) == cfg.MO_PATTERN["cases_from_hotspot"]
    for r in _rows(out, "CaseMaster"):
        if r["CaseMasterID"] in ids:
            assert "motorcycle" in r["BriefFacts"] and "gold chain" in r["BriefFacts"]


def test_identity_fragment_and_control_records(dataset):
    out, gen = dataset
    frag = gen.ground_truth["identity_fragment"]["records"]
    accused = {r["AccusedMasterID"]: r for r in _rows(out, "Accused")}
    names = {accused[str(f["accused_master_id"])]["AccusedName"] for f in frag}
    assert names == {"Ravi Kumar", "Ravi K", "Ravi Kumar S"}
    ctl = gen.ground_truth["same_name_control"]["records"]
    ages = {int(accused[str(c["accused_master_id"])]["AgeYear"]) for c in ctl}
    assert ages == {24, 52}  # contradictory ages — must not strong-match


def test_anomaly_case_features(dataset):
    out, gen = dataset
    a = gen.ground_truth["anomaly_case"]
    case = next(r for r in _rows(out, "CaseMaster")
                if r["CaseMasterID"] == str(a["case_id"]))
    assert datetime.fromisoformat(case["IncidentFromDate"]).hour == a["hour"]
    n_accused = sum(1 for r in _rows(out, "Accused")
                    if r["CaseMasterID"] == str(a["case_id"]))
    assert n_accused == a["accused_count"]


def test_dangling_courts_and_missing_coords_designed(dataset):
    out, gen = dataset
    dq = gen.ground_truth["data_quality"]
    cases = _rows(out, "CaseMaster")
    dangling = [r for r in cases if r["CourtID"] == "9999"]
    assert len(dangling) == cfg.DANGLING_COURT_CASES
    missing = sum(1 for r in cases if r["latitude"] == "")
    assert missing == dq["missing_coordinate_cases"]
    assert missing / len(cases) < cfg.MISSING_COORD_RATE * 2  # sane rate


def test_fk_integrity_except_designed_dangling(dataset):
    out, gen = dataset
    case_ids = {r["CaseMasterID"] for r in _rows(out, "CaseMaster")}
    unit_ids = {r["UnitID"] for r in _rows(out, "Unit")}
    for r in _rows(out, "Accused"):
        assert r["CaseMasterID"] in case_ids
    for r in _rows(out, "CaseMaster"):
        assert r["PoliceStationID"] in unit_ids


def test_engines_cannot_reference_ground_truth():
    """Guard: analytics engines never import datagen or read ground_truth."""
    analytics = ROOT / "backend/kavach/analytics"
    for f in analytics.rglob("*.py"):
        src = f.read_text()
        assert "datagen" not in src and "ground_truth" not in src, f


def test_crime_no_structured_format(dataset):
    out, _ = dataset
    district_of_unit = {u["UnitID"]: u["DistrictID"] for u in _rows(out, "Unit")}
    r = _rows(out, "CaseMaster")[0]
    crime_no, case_no = r["CrimeNo"], r["CaseNo"]
    # format: 1 category + 4 district + 4 unit + 4 year + 5 serial (matrix §1.1)
    assert len(crime_no) == 18 and crime_no[-9:] == case_no
    assert crime_no[1:5] == f"{int(district_of_unit[r['PoliceStationID']]):04d}"
    assert crime_no[5:9] == f"{int(r['PoliceStationID']):04d}"
    assert crime_no[9:13] == r["CrimeRegisteredDate"][:4]


def test_serials_are_per_station_category_year(dataset):
    out, _ = dataset
    seen: dict[tuple, list[int]] = {}
    for r in _rows(out, "CaseMaster"):
        key = (r["PoliceStationID"], r["CrimeNo"][0], r["CrimeNo"][9:13])
        seen.setdefault(key, []).append(int(r["CrimeNo"][-5:]))
    for serials in seen.values():
        assert sorted(serials) == list(range(1, len(serials) + 1))


def test_incident_dates_within_history(dataset):
    out, _ = dataset
    lo = cfg.ANCHOR - timedelta(days=cfg.HISTORY_DAYS + 2)
    for r in _rows(out, "CaseMaster"):
        occ = datetime.fromisoformat(r["IncidentFromDate"])
        assert lo <= occ <= cfg.ANCHOR
