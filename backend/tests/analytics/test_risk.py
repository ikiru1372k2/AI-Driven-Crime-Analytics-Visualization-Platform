"""Area-risk forecast validation (FORECAST tab).

Hermetic: generates a dataset, points the data layer at it, and injects a FAKE
QuickML client so we test OUR plumbing (feature parity, risk levels, drivers,
the honest unavailable state, the anti-hallucination fence) deterministically —
never Zoho's model, which is external and out of scope for unit tests.
"""

import os
from pathlib import Path

import pytest

from kavach.analytics.risk import MODEL_VERSION, features, forecast_area_risk
from kavach.analytics.risk.engine import _numbers_safe
from kavach.api import data
from kavach.api.envelope import envelope
from kavach.catalyst.quickml import QuickMLUnavailable
from kavach.config import settings
from kavach.datagen.generator import generate_dataset
from kavach.provenance import DataClassification

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "docs/schema/schema-manifest.json"


class FakeQuickML:
    """Stand-in for QuickMLClient: predict returns a deterministic function of
    the row; llm is configurable (unavailable by default)."""

    def __init__(self, predictor=None, *, predict_fail=False, llm_text=None):
        self._predictor = predictor or (lambda r: r["recent_count"] * 1.5 + 2)
        self._predict_fail = predict_fail
        self._llm_text = llm_text

    def predict(self, rows):
        if self._predict_fail:
            raise QuickMLUnavailable("stub: endpoint down")
        return [{features.TARGET_COLUMN: self._predictor(r)} for r in rows]

    def llm(self, prompt):
        if self._llm_text is None:
            raise QuickMLUnavailable("stub: llm not configured")
        return self._llm_text


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    out = tmp_path_factory.mktemp("risk_synth")
    generate_dataset(out, MANIFEST, seed=20260722, background_cases=800)
    prev = os.environ.get("KAVACH_DATA_DIR")
    os.environ["KAVACH_DATA_DIR"] = str(out)
    data.enriched_cases.cache_clear()
    yield out
    if prev is None:
        os.environ.pop("KAVACH_DATA_DIR", None)
    else:
        os.environ["KAVACH_DATA_DIR"] = prev
    data.enriched_cases.cache_clear()


def test_feature_rows_match_the_model_contract(planted):
    """Serving rows carry every FEATURE_COLUMN; training rows add the target.
    Train/serve parity is the whole point of the shared features module."""
    serving = features.serving_rows()
    assert serving, "expected per-district serving rows"
    for row in serving:
        for col in features.FEATURE_COLUMNS:
            assert col in row, f"serving row missing feature {col}"

    training = features.training_rows()
    assert training, "expected historical training rows"
    for row in training[:50]:
        for col in features.FEATURE_COLUMNS:
            assert col in row
        assert features.TARGET_COLUMN in row


def test_forecast_available_with_stub(planted):
    res = forecast_area_risk(quickml=FakeQuickML())
    assert res["available"] is True
    assert res["model_version"] == MODEL_VERSION
    assert res["districts"], "expected per-district forecasts"
    levels = {d["risk_level"] for d in res["districts"]}
    assert levels <= {"High", "Medium", "Low"}
    for d in res["districts"]:
        assert isinstance(d["expected_count"], int) and d["expected_count"] >= 0
        assert d["trend"] in {"up", "down", "flat"}
        assert d["drivers"], "every district must cite computed driver facts"
        assert d["summary"] and isinstance(d["summary"], str)
        assert d["confidence"]["level"] in {"high", "medium", "low"}
    # ranked by expected volume, descending
    counts = [d["expected_count"] for d in res["districts"]]
    assert counts == sorted(counts, reverse=True)


def test_unavailable_is_honest_no_fabricated_numbers(planted):
    res = forecast_area_risk(quickml=FakeQuickML(predict_fail=True))
    assert res["available"] is False
    assert res["districts"] == []
    assert res["reason"], "must explain why the forecast is unavailable"
    assert res["model_version"].endswith("unconfigured")
    # the unavailable payload can still carry an AI_DERIVED envelope (model_version
    # present) exactly as the route builds it — the guard must not raise.
    env = envelope(
        classification=DataClassification.AI_DERIVED,
        method_name="quickml_area_risk_forecast",
        method_version="1.0.0",
        model_version=res["model_version"],
    )
    assert env["classification"] == "AI_DERIVED"


def test_qwen_polish_is_fenced_against_invented_numbers(planted):
    """A Qwen sentence that introduces a number the facts didn't contain is
    rejected; a safe rephrase is accepted and attributed to the model."""
    # unsafe: injects "999" that never appears in any computed fact
    unsafe = forecast_area_risk(quickml=FakeQuickML(llm_text="Expect 999 incidents soon."))
    for d in unsafe["districts"]:
        assert d["summary_source"] == "template", "invented number must be rejected"
        assert "999" not in d["summary"]

    # safe: a number-free rephrase is accepted for the High-risk districts
    safe = forecast_area_risk(
        quickml=FakeQuickML(llm_text="Officers should stay alert in this area next month.")
    )
    polished = [d for d in safe["districts"] if d["summary_source"] != "template"]
    assert polished, "expected at least one High-risk district to be Qwen-polished"
    for d in polished:
        assert d["risk_level"] == "High"
        assert d["summary_source"] == settings.quickml_llm_model


def test_numbers_safe_guard():
    facts = "about 34 cases in the next 30 days (up 20%)"
    assert _numbers_safe("Around 34 cases expected within 30 days, up 20 percent.", facts)
    assert not _numbers_safe("About 50 cases next 30 days.", facts)  # 50 not in facts
    assert _numbers_safe("Activity is rising in this district.", facts)  # no numbers
