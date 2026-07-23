"""Background snapshot + cache warmer (PERF-001).

Moves the two slow, first-request-only costs OFF the request path, where they
otherwise exceed AppSail's 30s HTTP limit and time out:

1. **Cold Data Store read.** Reading every table (16.6k CaseMaster rows paged
   300 at a time over OAuth ZCQL, plus Accused/Victim) is ~30s+. Only relevant in
   Data Store mode; handled by publishing an in-memory ``snapshot`` that
   ``data._read`` / ``graph_store`` serve instantly.
2. **Entity resolution.** ``resolve_identities`` does an O(n²) pairwise compare
   over every accused record — ~13s on the deployed demo, longer on a cold
   Data Store read — and backs BOTH ``/identities`` and ``/associations`` (via the
   same-suspect channel). This is CPU-bound, so it is warmed in **every** mode.

A daemon thread does the work (not bound by the HTTP limit): on boot it primes
the caches, and in Data Store mode it also refreshes the snapshot every
``KAVACH_DATASTORE_TTL`` seconds, atomically swapping in fresh data. A failed
refresh keeps the last-good snapshot — the app never regresses to timeouts.

Skipped under pytest (``"pytest" in sys.modules``) so the test suite is never
slowed or raced by a background prime; set ``KAVACH_WARMER_FORCE=1`` to override
(the warmer's own test does this).
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time

from kavach.api import data, graph_store, snapshot
from kavach.config import settings
from kavach.ingestion.loader import LOAD_ORDER

log = logging.getLogger("kavach.warmer")

_thread: threading.Thread | None = None
_stop = threading.Event()

#: last prime outcome per step — {label: "1.2s" | "ERROR: ..."} plus a run ts.
#: Exposed via /health/snapshot so we can SEE whether the daemon actually
#: primed on AppSail (its background thread can be starved between requests).
_prime_log: dict[str, object] = {}


def status() -> dict:
    """What the warmer has done — for /health/snapshot diagnostics (PERF-001)."""
    return {"enabled": _enabled(), "datastore": _use_datastore(),
            "alive": bool(_thread and _thread.is_alive()), "last_prime": dict(_prime_log)}


def _use_datastore() -> bool:
    return settings.data_source.strip().lower() == "datastore"


def _enabled() -> bool:
    if os.environ.get("KAVACH_WARMER_FORCE") == "1":
        return True
    return "pytest" not in sys.modules


def _build_from_csv() -> dict:
    """Read every source table from the bundled CSVs (instant, no network)."""
    import pandas as pd

    tables: dict = {}
    base = data.data_dir()
    for name in LOAD_ORDER:
        path = base / f"{name}.csv"
        if path.exists():
            tables[name] = pd.read_csv(path, dtype=str, keep_default_na=False)
    return tables


def _build_from_datastore() -> dict:
    """Read every source table live from the Catalyst Data Store (slow, off-path)."""
    from kavach.api import datastore

    tables: dict = {}
    for name in LOAD_ORDER:
        tables[name] = datastore.read_table(name)
    return tables


def _clear_caches() -> None:
    """Drop the memoized builders so they recompute against fresh data."""
    from kavach.analytics.anomaly import engine as anomaly_engine
    from kavach.analytics.association import engine as association_engine
    from kavach.analytics.entity import resolve_identities
    from kavach.analytics.risk import engine as risk_engine

    data.enriched_cases.cache_clear()
    for name in ("case_narratives", "accused_records", "victim_records"):
        fn = getattr(data, name, None)
        clear = getattr(fn, "cache_clear", None)
        if clear:
            clear()
    resolve_identities.cache_clear()
    association_engine.cache_clear()  # people/rows/same-suspect/same-victim indices
    anomaly_engine._detect_cached.cache_clear()
    risk_engine._forecast_cached.cache_clear()
    graph_store.reset_graph_context()


def _prime() -> None:
    """Compute the expensive caches now, on this thread (off the request path).

    Ordered cheapest-first so an early failure still leaves the quick wins warm.
    Each step is independent and best-effort.
    """
    from kavach.analytics.anomaly.engine import detect_anomalies
    from kavach.analytics.entity import resolve_identities
    from kavach.analytics.risk.engine import forecast_area_risk

    for label, fn in (
        ("enriched_cases", data.enriched_cases),
        ("accused_records", getattr(data, "accused_records", None)),
        ("victim_records", getattr(data, "victim_records", None)),
        ("resolve_identities", resolve_identities),  # the ~90s O(n^2) step
        ("graph_context", graph_store.graph_context),
        # Model-backed analytics: memoized per default params so /anomalies and
        # /risk serve the warmed result instead of refitting / re-calling the
        # live model + LLM on the request path. Best-effort (skip if the live
        # model is unconfigured — the engines return available:false fast).
        ("anomaly_scan", detect_anomalies),
        ("area_risk_forecast", forecast_area_risk),
    ):
        if fn is None:
            continue
        try:
            t = time.time()
            fn()
            dt = time.time() - t
            _prime_log[label] = f"{dt:.1f}s"
            log.info("warmed %s in %.1fs", label, dt)
        except Exception as exc:  # noqa: BLE001 - never let the warmer thread die
            _prime_log[label] = f"ERROR: {type(exc).__name__}: {exc}"
            log.exception("warming %s failed", label)
    _prime_log["ran_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _publish(tables: dict, source: str) -> None:
    snapshot.publish(tables, source=source, ts=time.time())
    _clear_caches()
    _prime()
    log.info("snapshot published: source=%s tables=%d", source, len(tables))


def _warm_loop() -> None:
    """Daemon body: prime once, then (Data Store mode) refresh forever."""
    if _use_datastore():
        # Prime from the CSV bootstrap FIRST so /identities and /associations are
        # warm within ~a minute of boot (on bundled rows) instead of hitting a
        # cold ~90s entity-resolution during the ~30s live read below.
        _prime()
        # First live snapshot, then keep it fresh. The CSV bootstrap was already
        # published synchronously in start(), so requests serve immediately.
        try:
            _publish(_build_from_datastore(), source="datastore")
        except Exception:  # noqa: BLE001
            log.exception("initial datastore snapshot failed; serving CSV until next try")
        interval = max(settings.datastore_cache_ttl, 30.0)
        while not _stop.is_set():
            if _stop.wait(interval):
                break
            try:
                from kavach.api import datastore

                datastore.cache_clear()  # force a genuine re-read, not the TTL cache
                _publish(_build_from_datastore(), source="datastore")
            except Exception:  # noqa: BLE001
                log.exception("datastore refresh failed; keeping last-good snapshot")
    else:
        # CSV mode: no snapshot needed (bundled reads are instant), but the
        # CPU-bound entity resolution / graph build still must not hit a request
        # cold — prime them once here.
        _prime()


def start() -> None:
    """Prime caches off the request path; in Data Store mode also keep a snapshot.

    Idempotent and best-effort: any failure is logged and swallowed so app boot
    never blocks on the warmer. A no-op under pytest unless forced.
    """
    global _thread
    if not _enabled():
        return
    if _thread and _thread.is_alive():
        return

    # Data Store mode: publish an instant CSV bootstrap snapshot synchronously so
    # the very first request serves bundled rows (the store was seeded from them)
    # instead of blocking on the ~30s live read the daemon does next.
    if _use_datastore():
        try:
            snapshot.publish(_build_from_csv(), source="csv", ts=time.time())
        except Exception:  # noqa: BLE001
            log.exception("CSV warm-start failed; requests will fall back to source reads")

    _stop.clear()
    _thread = threading.Thread(target=_warm_loop, name="kavach-warmer", daemon=True)
    _thread.start()


def stop() -> None:
    """Signal the refresh loop to exit (lifespan shutdown / tests)."""
    _stop.set()
