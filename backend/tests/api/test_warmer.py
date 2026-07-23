"""Background warmer (PERF-001).

Network-free and thread-free: exercises the warmer's decision logic and its
best-effort priming/clearing, not the daemon loop. The point of the warmer is to
move the slow cold read + entity resolution OFF the request path, so the units
that matter here are: is it enabled, which source does it target, does priming
survive a failing builder, and does a snapshot publish reset the derived caches.
"""

from __future__ import annotations

import types

from kavach.api import data, snapshot, warmer


def test_disabled_under_pytest_by_default(monkeypatch):
    monkeypatch.delenv("KAVACH_WARMER_FORCE", raising=False)
    assert warmer._enabled() is False  # never slows/races the suite by default


def test_force_flag_enables_warmer(monkeypatch):
    monkeypatch.setenv("KAVACH_WARMER_FORCE", "1")
    assert warmer._enabled() is True  # the warmer's own integration test opts in


def test_use_datastore_follows_settings(monkeypatch):
    monkeypatch.setattr(warmer, "settings", types.SimpleNamespace(data_source="datastore"))
    assert warmer._use_datastore() is True
    monkeypatch.setattr(warmer, "settings", types.SimpleNamespace(data_source="CSV"))
    assert warmer._use_datastore() is False  # case-insensitive


def test_prime_is_best_effort_and_never_raises(monkeypatch):
    """A failing builder is logged and skipped — later builders still warm, and
    the thread body never propagates (it must not kill the daemon)."""
    calls: list[str] = []

    def boom():
        calls.append("enriched")
        raise RuntimeError("cold read blew up")

    monkeypatch.setattr(data, "enriched_cases", boom)
    # Stub the remaining builders so the test stays hermetic (no dataset needed).
    from kavach.analytics import entity
    from kavach.analytics.anomaly import engine as anomaly_engine
    from kavach.analytics.risk import engine as risk_engine
    from kavach.api import graph_store

    monkeypatch.setattr(data, "accused_records", lambda: calls.append("accused"))
    monkeypatch.setattr(data, "victim_records", lambda: calls.append("victim"))
    monkeypatch.setattr(entity, "resolve_identities", lambda: calls.append("identities"))
    monkeypatch.setattr(graph_store, "graph_context", lambda: calls.append("graph"))
    monkeypatch.setattr(anomaly_engine, "detect_anomalies", lambda: calls.append("anomaly"))
    monkeypatch.setattr(risk_engine, "forecast_area_risk", lambda: calls.append("risk"))

    warmer._prime()  # must not raise even though the first builder throws

    assert "enriched" in calls  # the failing one was attempted
    assert {"accused", "victim", "identities", "graph", "anomaly", "risk"} <= set(calls)


def test_publish_swaps_snapshot_and_clears_caches(monkeypatch):
    """Publishing a snapshot must reset the derived caches so the next read sees
    the fresh tables — assert every clear hook is invoked."""
    import pandas as pd

    cleared: list[str] = []

    def _tracker(label):
        return types.SimpleNamespace(cache_clear=lambda: cleared.append(label))

    monkeypatch.setattr(data, "enriched_cases", _tracker("enriched"))
    monkeypatch.setattr(data, "accused_records", _tracker("accused"))
    monkeypatch.setattr(data, "victim_records", _tracker("victim"))
    monkeypatch.setattr(data, "case_narratives", _tracker("narratives"))

    from kavach.analytics import entity
    from kavach.analytics.anomaly import engine as anomaly_engine
    from kavach.analytics.risk import engine as risk_engine
    from kavach.api import graph_store

    monkeypatch.setattr(entity, "resolve_identities", _tracker("identities"))
    monkeypatch.setattr(
        anomaly_engine, "_detect_cached", _tracker("anomaly_cache")
    )
    monkeypatch.setattr(risk_engine, "_forecast_cached", _tracker("risk_cache"))
    monkeypatch.setattr(graph_store, "reset_graph_context", lambda: cleared.append("graph"))
    monkeypatch.setattr(warmer, "_prime", lambda: None)  # isolate: test only the clear

    tables = {"District": pd.DataFrame({"DistrictID": ["1"]})}
    warmer._publish(tables, source="datastore")

    assert snapshot.is_ready() and snapshot.status()["source"] == "datastore"
    assert {
        "enriched", "accused", "victim", "narratives",
        "identities", "anomaly_cache", "risk_cache", "graph",
    } <= set(cleared)
    snapshot.clear()
