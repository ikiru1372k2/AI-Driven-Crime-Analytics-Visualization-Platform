"""Area-risk forecast (FORECAST tab) — QuickML predictor + plain-English facts.

The number is Zoho's, not ours. Per district we build a small count-based
feature row (see features.py), send it live to a trained QuickML pipeline
(``app.quick_ml().predict``), and get the predicted number of cases for the
next 30 days. We deliberately do NOT model locally: a hand-rolled regressor on
synthetic data would look authoritative without being trustworthy.

Around that number we compute only *facts* the officer can check — momentum vs
the previous window, the forecast's direction, the most frequent recent offence
— and phrase them in plain English. An optional Qwen 2.5 pass (Catalyst LLM
Serving) rewrites that sentence more naturally, but it is fenced: its output is
rejected if it contains any number the facts did not, so the model can never
change a forecast. When QuickML is unconfigured or unreachable (local dev, CI),
the result is an honest ``available: false`` — never a fabricated number.

Data is SYNTHETIC (ADR-011). This module never reads the generator's answer key.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

import numpy as np

from kavach.analytics.risk import features
from kavach.api import data
from kavach.catalyst.quickml import QuickMLClient, QuickMLUnavailable
from kavach.config import settings

logger = logging.getLogger(__name__)

#: Provenance identity (PROV-002 envelope). method_* describes our pipeline;
#: model_version identifies the external QuickML model that produced the number.
METHOD_NAME = "quickml_area_risk_forecast"
METHOD_VERSION = "1.0.0"
MODEL_VERSION = "quickml:area-risk-forecast:v1"
_UNCONFIGURED_MODEL = "quickml:area-risk:unconfigured"

#: Only the highest-risk districts get a Qwen phrasing call (bounds latency);
#: the rest keep the deterministic sentence. Both are honest — same facts.
_MAX_LLM_POLISH = 6


def _default_client() -> QuickMLClient:
    return QuickMLClient(
        risk_endpoint=settings.quickml_risk_endpoint,
        risk_url=settings.quickml_risk_url,
        client_id=settings.zoho_client_id,
        client_secret=settings.zoho_client_secret,
        refresh_token=settings.zoho_refresh_token,
        accounts_url=settings.zoho_accounts_url,
        org_id=settings.quickml_org_id,
        environment=settings.quickml_environment,
        llm_endpoint=settings.quickml_llm_endpoint,
        llm_token=settings.quickml_llm_token,
    )


def forecast_area_risk(*, window_days: int = 30, quickml: QuickMLClient | None = None) -> dict:
    """Per-district next-``window_days`` risk forecast via live QuickML.

    Args:
        window_days: forecast horizon and the feature window length.
        quickml: injected client (tests pass a fake); defaults to one built
            from settings.
    """
    client = quickml if quickml is not None else _default_client()
    rows = features.serving_rows(window_days)
    feature_rows = [{c: r[c] for c in features.FEATURE_COLUMNS} for r in rows]

    try:
        predictions = client.predict(feature_rows)
    except QuickMLUnavailable as exc:
        logger.info("area-risk forecast unavailable: %s", exc)
        return {
            "synthetic": True,
            "available": False,
            "reason": str(exc),
            "window_days": window_days,
            "model_version": _UNCONFIGURED_MODEL,
            "districts": [],
        }

    expected = [_extract_prediction(p) for p in predictions]
    if any(v is None for v in expected):
        return {
            "synthetic": True,
            "available": False,
            "reason": "QuickML returned an unrecognised prediction shape",
            "window_days": window_days,
            "model_version": _UNCONFIGURED_MODEL,
            "districts": [],
        }

    thresholds = _risk_thresholds([v for v in expected if v is not None])
    context = _recent_context(window_days)

    districts = []
    for row, pred in zip(rows, expected, strict=True):
        districts.append(
            _build_district(row, float(pred), thresholds, context, window_days)
        )
    districts.sort(key=lambda d: d["expected_count"], reverse=True)

    _polish_summaries(districts, client)

    for rank, d in enumerate(districts, 1):
        d["rank"] = rank
    return {
        "synthetic": True,
        "available": True,
        "window_days": window_days,
        "model_version": MODEL_VERSION,
        "district_count": len(districts),
        "districts": districts,
    }


def _extract_prediction(result: dict) -> float | None:
    """Pull the numeric forecast out of a QuickML predict result, tolerantly.

    QuickML regression returns the value in a single-element list
    (``{"result": [39.2], "status": "success"}``), so every candidate is passed
    through :func:`_first` to unwrap that before coercing to a number.
    """
    if not isinstance(result, dict):
        return _num(_first(result))
    for key in (features.TARGET_COLUMN, "prediction", "predicted_value", "output", "result"):
        if key in result:
            val = _num(_first(result[key]))
            if val is not None:
                return val
    # last resort: the single numeric value in the payload
    nums = [v for v in (_num(_first(x)) for x in result.values()) if v is not None]
    return nums[0] if len(nums) == 1 else None


def _first(x):
    """Unwrap a one-element list/tuple to its element; pass anything else through."""
    if isinstance(x, (list, tuple)) and len(x) == 1:
        return x[0]
    return x


def _num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if (np.isnan(v) or np.isinf(v)) else v


def _risk_thresholds(values: list[float]) -> tuple[float, float]:
    """Cross-district tertiles of expected volume (q1, q2)."""
    if not values:
        return (0.0, 0.0)
    return (float(np.quantile(values, 1 / 3)), float(np.quantile(values, 2 / 3)))


def _level(expected: float, thresholds: tuple[float, float]) -> str:
    q1, q2 = thresholds
    if expected >= q2:
        return "High"
    if expected >= q1:
        return "Medium"
    return "Low"


def _recent_context(window_days: int) -> dict[str, dict]:
    """Per-district recent-window context: top offence + sample case ids.

    These are checkable facts drawn straight from the source cases — the top
    offence explains the forecast in plain terms, and the sample ids let an
    officer open the actual FIRs behind a district's number (evidence trail).
    """
    df = data.enriched_cases()
    df = df[df["registered_date"].notna()]
    if df.empty:
        return {}
    latest = df["registered_date"].max()
    recent = df[df["registered_date"] > latest - np.timedelta64(window_days, "D")]
    out: dict[str, dict] = {}
    for did, grp in recent.groupby("district_id"):
        names = Counter(grp["subhead_name"].dropna())
        newest = grp.sort_values("registered_date", ascending=False)
        out[str(did)] = {
            "top_offence": names.most_common(1)[0][0] if names else None,
            "sample_case_ids": newest["CaseMasterID"].head(6).tolist(),
        }
    return out


def _build_district(
    row: dict,
    expected: float,
    thresholds: tuple[float, float],
    context: dict[str, dict],
    window_days: int,
) -> dict:
    recent = int(row["recent_count"])
    prior = int(row["prior_count"])
    expected_count = max(0, int(round(expected)))

    forecast_pct = _pct(expected_count, recent)
    momentum_pct = _pct(recent, prior)
    trend = "up" if forecast_pct >= 10 else "down" if forecast_pct <= -10 else "flat"
    level = _level(expected, thresholds)
    ctx = context.get(row["district_id"], {})
    top_offence = ctx.get("top_offence")

    drivers = _drivers(recent, prior, momentum_pct, forecast_pct, top_offence, window_days)
    confidence = _confidence(int(row["active_windows"]), recent)
    summary = _template_summary(
        row["district_name"], expected_count, forecast_pct, top_offence, window_days
    )
    return {
        "district_id": row["district_id"],
        "district_name": row["district_name"],
        "risk_level": level,
        "expected_count": expected_count,
        "recent_count": recent,
        "trend": trend,
        "forecast_pct_change": forecast_pct,
        "drivers": drivers,
        "summary": summary,
        "summary_source": "template",
        "confidence": confidence,
        "sample_case_ids": ctx.get("sample_case_ids", []),
    }


def _pct(new: float, base: float) -> int:
    if base <= 0:
        return 0
    return int(round((new - base) / base * 100))


def _drivers(
    recent: int,
    prior: int,
    momentum_pct: int,
    forecast_pct: int,
    top_offence: str | None,
    window_days: int,
) -> list[str]:
    d: list[str] = []
    if forecast_pct >= 10:
        d.append(f"Forecast up {forecast_pct}% vs the last {window_days} days")
    elif forecast_pct <= -10:
        d.append(f"Forecast down {abs(forecast_pct)}% vs the last {window_days} days")
    else:
        d.append(f"Forecast steady vs the last {window_days} days")
    if prior > 0 and abs(momentum_pct) >= 10:
        direction = "rose" if momentum_pct > 0 else "fell"
        d.append(f"Cases {direction} {abs(momentum_pct)}% over the previous 30 days")
    d.append(f"{recent} cases in the last {window_days} days")
    if top_offence:
        d.append(f"Most frequent recent offence: {top_offence}")
    return d


def _confidence(active_windows: int, recent: int) -> dict:
    if active_windows >= 6 and recent >= 10:
        level = "high"
    elif active_windows >= 3 and recent >= 3:
        level = "medium"
    else:
        level = "low"
    basis = f"{active_windows} active periods of history, {recent} recent cases"
    return {"level": level, "basis": basis}


def _template_summary(
    name: str, expected: int, forecast_pct: int, top_offence: str | None, window_days: int
) -> str:
    if forecast_pct >= 10:
        move = f"up {forecast_pct}% from the last {window_days} days"
    elif forecast_pct <= -10:
        move = f"down {abs(forecast_pct)}% from the last {window_days} days"
    else:
        move = f"about the same as the last {window_days} days"
    tail = f", mostly {top_offence}" if top_offence else ""
    return (
        f"{name} is expected to see about {expected} cases in the next "
        f"{window_days} days ({move}){tail}."
    )


# --- optional Qwen phrasing (fenced against invented numbers) --------------
def _polish_summaries(districts: list[dict], client: QuickMLClient) -> None:
    """Rewrite the top districts' sentences with Qwen — keep template on any
    failure or if the model introduces a number the facts did not contain."""
    polished = 0
    for d in districts:
        if polished >= _MAX_LLM_POLISH or d["risk_level"] != "High":
            continue
        prompt = (
            "You are helping a senior police officer. Rewrite the following as ONE "
            "short, plain-English sentence. Use ONLY the numbers given; do not add, "
            "remove, or change any number.\nFacts: " + d["summary"]
        )
        try:
            candidate = client.llm(prompt)
        except QuickMLUnavailable as exc:
            logger.info("Qwen phrasing unavailable, keeping template: %s", exc)
            return  # first failure decides it for the whole response
        if _numbers_safe(candidate, d["summary"]):
            d["summary"] = candidate.strip()
            d["summary_source"] = settings.quickml_llm_model
            polished += 1


def _numbers_safe(candidate: str, facts: str) -> bool:
    """True if every number in the candidate also appears in the facts."""
    allowed = set(re.findall(r"\d+(?:\.\d+)?", facts))
    return all(n in allowed for n in re.findall(r"\d+(?:\.\d+)?", candidate))
