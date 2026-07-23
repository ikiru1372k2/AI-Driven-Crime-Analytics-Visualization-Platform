"""Anomaly detection validation (FLAG tab, C2-R10).

Generates a synthetic dataset, points the data layer at it, and asserts the
engine DISCOVERS the planted behaviourally-deviant case (a pre-dawn robbery with
an unusual number of accused) while a fake QuickML client keeps the GLM fence
deterministic. The planted answer key is read *here* only to assert detection —
the engine never sees it (ADR-011).
"""

import json
import os
from pathlib import Path

import pytest

from kavach.analytics.anomaly import MODEL_VERSION, detect_anomalies
from kavach.analytics.anomaly.engine import _numbers_safe
from kavach.api import data
from kavach.catalyst.quickml import QuickMLUnavailable
from kavach.config import settings
from kavach.datagen.generator import generate_dataset

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"


class FakeQuickML:
    """Stand-in for QuickMLClient: only ``llm`` is exercised here (detection is
    pure statistics + sklearn and needs no external call). Unavailable by default."""

    def __init__(self, *, llm_text=None):
        self._llm_text = llm_text

    def llm(self, prompt):
        if self._llm_text is None:
            raise QuickMLUnavailable("stub: llm not configured")
        return self._llm_text


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    out = tmp_path_factory.mktemp("anomaly_synth")
    generate_dataset(out, MANIFEST, seed=20260722, background_cases=800)
    prev = os.environ.get("KAVACH_DATA_DIR")
    os.environ["KAVACH_DATA_DIR"] = str(out)
    data.enriched_cases.cache_clear()
    answer = json.loads((out / "ground_truth.json").read_text())["anomaly_case"]
    yield answer
    if prev is None:
        os.environ.pop("KAVACH_DATA_DIR", None)
    else:
        os.environ["KAVACH_DATA_DIR"] = prev
    data.enriched_cases.cache_clear()


def _find(flags, case_id):
    cid = str(case_id)
    return next(
        (f for f in flags if cid in [str(x) for x in f["sample_case_ids"]]), None
    )


def test_detects_planted_anomaly(planted):
    res = detect_anomalies(quickml=FakeQuickML())
    flag = _find(res["flags"], planted["case_id"])
    assert flag is not None, "planted deviant case was not flagged"
    assert flag["score"] >= 2.5
    assert flag["severity"] in {"warning", "serious", "critical"}
    # its defining oddity is the unusual number of accused (6 vs the usual ~1)
    assert "many_accused" in flag["signals"]
    # and the ML model independently agrees the case is an outlier
    assert flag["ml_confirmed"] is True


def test_flags_carry_checkable_reason_and_evidence(planted):
    res = detect_anomalies(quickml=FakeQuickML())
    assert res["flag_count"] >= 1
    for f in res["flags"]:
        assert f["reason"], "every flag must carry a human-checkable reason"
        assert f["severity"] in {"warning", "serious", "critical"}
        assert f["sample_case_ids"], "every flag must cite evidence FIRs"
        assert f["subject"]["station_name"]
        assert f["type"] in {"many_accused", "odd_hour", "rare_offence"}
    scores = [f["score"] for f in res["flags"]]
    assert scores == sorted(scores, reverse=True), "flags must be ranked by score"


def test_model_version_and_synthetic_marker(planted):
    res = detect_anomalies(quickml=FakeQuickML())
    assert res["model_version"] == MODEL_VERSION
    assert res["synthetic"] is True


def test_threshold_suppresses(planted):
    # a score threshold above any real deviation removes every flag
    assert detect_anomalies(quickml=FakeQuickML(), min_score=100)["flag_count"] == 0


def test_max_flags_caps_output(planted):
    res = detect_anomalies(quickml=FakeQuickML(), min_score=0.0, max_flags=3)
    assert res["flag_count"] <= 3


def test_glm_phrasing_is_fenced_against_invented_numbers(planted):
    # unsafe: a sentence introducing a number no fact contains is rejected
    unsafe = detect_anomalies(quickml=FakeQuickML(llm_text="This case involves 999 suspects."))
    assert unsafe["flags"], "expected flags to phrase"
    assert all(f["explanation_source"] == "template" for f in unsafe["flags"])
    assert all("999" not in f["reason"] for f in unsafe["flags"])

    # safe: a number-free rephrase is accepted and attributed to the model
    safe = detect_anomalies(
        quickml=FakeQuickML(llm_text="This case stands out and is worth a closer look.")
    )
    polished = [f for f in safe["flags"] if f["explanation_source"] != "template"]
    assert polished, "expected a number-free rephrase to be accepted"
    assert all(f["explanation_source"] == settings.quickml_llm_model for f in polished)


def test_numbers_safe_guard():
    facts = "6 accused named at a station with 20 cases"
    assert _numbers_safe("There were 6 accused across 20 cases.", facts)
    assert not _numbers_safe("There were 99 accused.", facts)  # 99 not in facts
    assert _numbers_safe("This case is unusual.", facts)  # no numbers
