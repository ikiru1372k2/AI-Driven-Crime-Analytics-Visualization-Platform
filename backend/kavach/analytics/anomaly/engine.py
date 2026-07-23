"""Anomaly detection (FLAG tab, C2-R10) — surface cases that don't fit the pattern.

Hotspots say *where* crime concentrates, trends say *what is rising*, the
forecast says *how many next month*. None of them answer **"what is strange?"** —
the single FIR whose attributes are out of place for its station and offence.
This engine finds those *point anomalies* and ranks them as review leads.

Two detectors run together, and each carries its own honesty:

* **Transparent statistics** score every case against robust baselines (median +
  MAD modified z-score, the same idiom as the trends engine) on interpretable
  axes — number of accused, time of day, and how rare the offence is at that
  station. Each flag therefore carries a human-checkable *reason*; an officer can
  justify acting on it.
* **A real ML model** — scikit-learn ``IsolationForest`` (already used for DBSCAN
  hotspots) — learns the joint "normal" across those axes and flags cases that
  don't fit. When the ML agrees with the statistics a flag is marked
  ``ml_confirmed`` (higher confidence); the ML never overrides the explainable
  ranking, so nothing is flagged for a reason we cannot state.

An optional GLM-4.7 pass (Catalyst LLM Serving) rewrites each reason in plainer
English, fenced against inventing numbers exactly like the forecast summaries;
on any failure the deterministic sentence is kept. The statistics run fully
offline, so the tab always shows real flags — only the phrasing degrades.

Data is SYNTHETIC (ADR-011). This module reads cases only; it never reads the
generator's planted answer key.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from kavach.api import data
from kavach.catalyst.quickml import QuickMLClient, QuickMLUnavailable
from kavach.config import settings

logger = logging.getLogger(__name__)

#: Provenance identity (PROV-002 envelope). method_* describes our pipeline;
#: model_version identifies the ML model that corroborates each flag.
METHOD_NAME = "robust_point_anomaly"
METHOD_VERSION = "1.0.0"
MODEL_VERSION = "sklearn-isolationforest:anomaly:v1"

#: 0.6745 = 0.75 quantile of the normal; scales MAD to a std-equivalent so the
#: modified z-score reads like an ordinary z-score.
_MAD_TO_SIGMA = 1.4826
#: Floors on robust spread — counts/hours are low-cardinality, so a near-constant
#: baseline would otherwise make z explode on any wobble.
_ACCUSED_SIGMA_FLOOR = 1.0
_HOUR_SIGMA_FLOOR = 1.5

#: z-score cut points -> severity (aligned to the status palette good->critical).
_SEVERITY = [(5.0, "critical"), (3.5, "serious"), (2.5, "warning")]

#: A baseline needs at least this many observations to be trustworthy.
_MIN_ACCUSED_BASELINE = 10
_MIN_HOUR_BASELINE = 8
#: Offence-rarity guards: only flag "rare here" when the station is well observed
#: and the offence is common enough elsewhere to expect it.
_MIN_STATION_CASES = 20
_MIN_GLOBAL_SHARE = 0.01
#: Only the top flags get a GLM phrasing call (bounds latency); the rest keep the
#: deterministic sentence. Both are honest — same facts.
_MAX_LLM_POLISH = 8


def _severity(z: float) -> str | None:
    for threshold, label in _SEVERITY:
        if z >= threshold:
            return label
    return None


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
        llm_model=settings.quickml_llm_model_id,
    )


def detect_anomalies(
    *,
    window_days: int = 30,
    min_score: float = 2.5,
    max_flags: int = 25,
    quickml: QuickMLClient | None = None,
) -> dict:
    """Rank recent cases whose attributes are out of place for their context.

    Args:
        window_days: only cases registered in this trailing window are candidate
            flags; baselines are always computed over the full history.
        min_score: modified z-score a signal must reach to raise a flag.
        max_flags: cap on the number of ranked flags returned.
        quickml: injected client (tests pass a fake); defaults to one from settings.
    """
    params = {"window_days": window_days, "min_score": min_score, "max_flags": max_flags}
    df = data.enriched_cases()
    df = df[df["registered_date"].notna() & df["station_id"].notna()].copy()
    if df.empty:
        return _empty(params)

    df["accused_count"] = _accused_counts(df)
    df["hour"] = _incident_hour(df)
    df["gravity_rank"] = pd.Categorical(df["gravity"].fillna("")).codes

    latest = df["registered_date"].max()
    recent_cut = latest - pd.Timedelta(days=window_days)
    candidates = df[df["registered_date"] > recent_cut].copy()
    if candidates.empty:
        return _empty(params)

    baselines = _build_baselines(df)
    ml_flags = _isolation_forest(df, candidates)

    flags: list[dict] = []
    for _, case in candidates.iterrows():
        signals = _score_case(case, baselines, min_score)
        if not signals:
            continue
        flags.append(_build_flag(case, signals, ml_flags))

    flags = _dedupe_rare_offence(flags)
    flags.sort(key=lambda f: f["score"], reverse=True)
    flags = flags[:max_flags]

    client = quickml if quickml is not None else _default_client()
    _polish_reasons(flags, client)

    for rank, f in enumerate(flags, 1):
        f["rank"] = rank
    return {
        "synthetic": True,
        "params": params,
        "model_version": MODEL_VERSION,
        "flag_count": len(flags),
        "flags": flags,
    }


def _empty(params: dict) -> dict:
    return {
        "synthetic": True,
        "params": params,
        "model_version": MODEL_VERSION,
        "flag_count": 0,
        "flags": [],
    }


# --- feature preparation ---------------------------------------------------
def _accused_counts(df: pd.DataFrame) -> pd.Series:
    """Number of accused per case (0 where none), aligned to ``df``'s index."""
    counts = Counter(str(r["case_id"]) for r in data.accused_records())
    return df["CaseMasterID"].astype(str).map(lambda cid: counts.get(cid, 0)).astype(int)


def _incident_hour(df: pd.DataFrame) -> pd.Series:
    """Hour of the incident (fallback to the registration timestamp)."""
    hour = df["incident_from"].dt.hour
    return hour.fillna(df["registered_date"].dt.hour).astype("Int64")


# --- baselines (full history) ----------------------------------------------
def _build_baselines(df: pd.DataFrame) -> dict:
    """Robust per-context baselines used to score each candidate case."""
    accused_by_subhead: dict[str, tuple[float, float]] = {}
    for sub, grp in df.groupby("subhead_id"):
        vals = grp["accused_count"].to_numpy()
        if len(vals) >= _MIN_ACCUSED_BASELINE:
            accused_by_subhead[str(sub)] = _robust_center_sigma(vals, _ACCUSED_SIGMA_FLOOR)

    hour_by_pair: dict[tuple[str, str], tuple[float, float]] = {}
    hour_by_subhead: dict[str, tuple[float, float]] = {}
    for sub, grp in df.groupby("subhead_id"):
        hours = grp["hour"].dropna().to_numpy(dtype=float)
        if len(hours) >= _MIN_HOUR_BASELINE:
            hour_by_subhead[str(sub)] = _circular_center_sigma(hours)
    for (station, sub), grp in df.groupby(["station_id", "subhead_id"]):
        hours = grp["hour"].dropna().to_numpy(dtype=float)
        if len(hours) >= _MIN_HOUR_BASELINE:
            hour_by_pair[(str(station), str(sub))] = _circular_center_sigma(hours)

    total = len(df)
    global_share = {str(s): len(g) / total for s, g in df.groupby("subhead_id")}
    station_total = {str(s): len(g) for s, g in df.groupby("station_id")}
    pair_count = {
        (str(st), str(sb)): len(g) for (st, sb), g in df.groupby(["station_id", "subhead_id"])
    }
    return {
        "accused_by_subhead": accused_by_subhead,
        "hour_by_pair": hour_by_pair,
        "hour_by_subhead": hour_by_subhead,
        "global_share": global_share,
        "station_total": station_total,
        "pair_count": pair_count,
    }


def _robust_center_sigma(values: np.ndarray, floor: float) -> tuple[float, float]:
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return median, max(mad * _MAD_TO_SIGMA, floor)


def _circular_center_sigma(hours: np.ndarray) -> tuple[float, float]:
    """Circular mean hour + a robust spread, so 23:00 and 01:00 read as close."""
    angles = hours * (2 * np.pi / 24)
    center_angle = np.arctan2(np.sin(angles).mean(), np.cos(angles).mean())
    center = float((center_angle % (2 * np.pi)) * 24 / (2 * np.pi))
    dists = np.array([_circular_hour_dist(h, center) for h in hours])
    mad = float(np.median(dists))
    return center, max(mad * _MAD_TO_SIGMA, _HOUR_SIGMA_FLOOR)


def _circular_hour_dist(a: float, b: float) -> float:
    d = abs(a - b) % 24
    return min(d, 24 - d)


# --- per-case scoring ------------------------------------------------------
def _score_case(case: pd.Series, baselines: dict, min_score: float) -> list[dict]:
    """Every signal that crosses ``min_score`` for one case, richest first."""
    sub = str(case["subhead_id"])
    station = str(case["station_id"])
    signals: list[dict] = []

    acc_base = baselines["accused_by_subhead"].get(sub)
    accused = int(case["accused_count"])
    if acc_base:
        median, sigma = acc_base
        z = (accused - median) / sigma
        if z >= min_score:
            signals.append({
                "type": "many_accused",
                "score": round(z, 2),
                "reason": (
                    f"{accused} accused named — {case['subhead_name']} at "
                    f"{case['station_name']} usually involves about {int(round(median))}."
                ),
            })

    hour = case["hour"]
    hour_base = baselines["hour_by_pair"].get((station, sub)) or baselines[
        "hour_by_subhead"
    ].get(sub)
    if hour_base is not None and not pd.isna(hour):
        center, sigma = hour_base
        dist = _circular_hour_dist(float(hour), center)
        z = dist / sigma
        if z >= min_score:
            signals.append({
                "type": "odd_hour",
                "score": round(z, 2),
                "reason": (
                    f"Registered around {int(hour) % 24:02d}:00 — {case['subhead_name']} at "
                    f"{case['station_name']} usually occurs near {int(round(center)) % 24:02d}:00."
                ),
            })

    rare = _rare_offence_signal(case, baselines, min_score)
    if rare:
        signals.append(rare)

    # Point signals (properties of this FIR) headline over the contextual
    # rare-offence signal (a property of the station×offence pair); within a
    # priority band the stronger z leads. This keeps a case-specific oddity
    # (e.g. six accused) from being demoted — and later swept into the
    # rare-offence dedup — just because "rare here" scored marginally higher.
    signals.sort(key=lambda s: (_SIGNAL_PRIORITY[s["type"]], -s["score"]))
    return signals


def _rare_offence_signal(case: pd.Series, baselines: dict, min_score: float) -> dict | None:
    """Flag an offence that is under-represented at this station yet just occurred."""
    sub = str(case["subhead_id"])
    station = str(case["station_id"])
    n_station = baselines["station_total"].get(station, 0)
    p_global = baselines["global_share"].get(sub, 0.0)
    if n_station < _MIN_STATION_CASES or p_global < _MIN_GLOBAL_SHARE:
        return None
    expected = n_station * p_global
    observed = baselines["pair_count"].get((station, sub), 0)
    if expected < 3 or observed > expected * 0.4:
        return None
    z = (expected - observed) / np.sqrt(expected)
    if z < min_score:
        return None
    pct = round(observed / n_station * 100, 1)
    return {
        "type": "rare_offence",
        "score": round(float(z), 2),
        "reason": (
            f"{case['subhead_name']} is rare at {case['station_name']} "
            f"({pct}% of its cases) — an out-of-place offence here."
        ),
    }


# --- ML corroboration ------------------------------------------------------
def _isolation_forest(df: pd.DataFrame, candidates: pd.DataFrame) -> set[str]:
    """Case ids the ML model judges outliers (multivariate, over all history).

    Fitting on the full history and predicting the candidates keeps the notion of
    "normal" stable. ``random_state`` is pinned so the result is deterministic
    (tests depend on it). Returns the set of candidate CaseMasterIDs the model
    marks as anomalies.
    """
    feats = ["accused_count", "hour", "gravity_rank"]
    train = df[feats].copy()
    train["hour"] = train["hour"].astype(float).fillna(train["hour"].astype(float).median())
    if len(train) < 20:
        return set()
    model = IsolationForest(n_estimators=200, contamination="auto", random_state=0)
    model.fit(train.to_numpy())

    cand = candidates[feats].copy()
    cand["hour"] = cand["hour"].astype(float).fillna(train["hour"].median())
    preds = model.predict(cand.to_numpy())
    return {
        str(cid)
        for cid, p in zip(candidates["CaseMasterID"].astype(str), preds, strict=True)
        if p == -1
    }


def _build_flag(case: pd.Series, signals: list[dict], ml_flags: set[str]) -> dict:
    dominant = signals[0]
    case_id = str(case["CaseMasterID"])
    when = case["incident_from"] if not pd.isna(case["incident_from"]) else case["registered_date"]
    return {
        "case_id": case_id,
        "type": dominant["type"],
        "title": _TITLES[dominant["type"]],
        "severity": _severity(dominant["score"]),
        "score": dominant["score"],
        "reason": " ".join(s["reason"] for s in signals),
        "signals": [s["type"] for s in signals],
        "explanation_source": "template",
        "ml_confirmed": case_id in ml_flags,
        "subject": {
            "station_id": str(case["station_id"]),
            "station_name": case["station_name"],
            "district_name": case["district_name"],
            "subhead_id": str(case["subhead_id"]),
            "subhead_name": case["subhead_name"],
        },
        "when": None if pd.isna(when) else when.strftime("%Y-%m-%d %H:%M"),
        "sample_case_ids": [case_id],
    }


_TITLES = {
    "many_accused": "Unusually many accused",
    "odd_hour": "Unusual timing",
    "rare_offence": "Out-of-place crime type",
}

#: Lower headlines the flag. Point signals (per-FIR) lead the contextual
#: rare-offence signal (per station×offence), which is what gets deduped.
_SIGNAL_PRIORITY = {"many_accused": 0, "odd_hour": 0, "rare_offence": 1}


def _dedupe_rare_offence(flags: list[dict]) -> list[dict]:
    """Keep one rare-offence flag per station+offence (the strongest), collecting
    the others' case ids as evidence; case-specific flags pass through as-is."""
    best: dict[tuple[str, str], dict] = {}
    out: list[dict] = []
    for f in flags:
        if f["type"] != "rare_offence":
            out.append(f)
            continue
        key = (f["subject"]["station_id"], f["subject"]["subhead_id"])
        keep = best.get(key)
        if keep is None:
            best[key] = f
            out.append(f)
        else:
            keep["sample_case_ids"] = (keep["sample_case_ids"] + f["sample_case_ids"])[:10]
            if f["score"] > keep["score"]:
                keep["score"], keep["reason"] = f["score"], f["reason"]
                keep["severity"] = _severity(f["score"])
    return out


# --- optional GLM phrasing (fenced against invented numbers) ----------------
def _polish_reasons(flags: list[dict], client: QuickMLClient) -> None:
    """Rewrite the top flags' reasons with GLM — keep the template on any failure
    or if the model introduces a number the facts did not contain."""
    polished = 0
    for f in flags:
        if polished >= _MAX_LLM_POLISH:
            return
        prompt = (
            "You are helping a senior police officer triage unusual cases. Rewrite "
            "the following as ONE short, plain-English sentence explaining why the "
            "case is unusual. Use ONLY the numbers given; do not add, remove, or "
            "change any number.\nFacts: " + f["reason"]
        )
        try:
            candidate = client.llm(prompt)
        except QuickMLUnavailable as exc:
            logger.info("GLM phrasing unavailable, keeping templates: %s", exc)
            return  # first failure decides it for the whole response
        if candidate and _numbers_safe(candidate, f["reason"]):
            f["reason"] = candidate.strip()
            f["explanation_source"] = settings.quickml_llm_model
            polished += 1


def _numbers_safe(candidate: str, facts: str) -> bool:
    """True if every number in the candidate also appears in the facts."""
    allowed = set(re.findall(r"\d+(?:\.\d+)?", facts))
    return all(n in allowed for n in re.findall(r"\d+(?:\.\d+)?", candidate))
