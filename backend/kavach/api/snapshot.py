"""In-memory published snapshot of the source tables (PERF-001).

Keeps the slow whole-dataset read OFF the request path. The Data Store read is
~30s cold (16.6k CaseMaster rows paged 300 at a time over OAuth ZCQL) — longer
than AppSail's 30s HTTP limit, so doing it inside a request handler times out and
the cache never warms. Instead, ``warmer.py`` reads the tables on a background
thread (not bound by the HTTP limit) and **publishes** them here; ``data._read``
and ``graph_store`` then serve from this in-memory copy instantly.

This module is a leaf (only stdlib + pandas) so ``data.py`` can import it without
a cycle. It holds *raw* source tables shaped exactly like the CSVs — the joins in
``data.enriched_cases`` run on top, unchanged.
"""

from __future__ import annotations

import threading

import pandas as pd

_lock = threading.Lock()
_tables: dict[str, pd.DataFrame] | None = None
_source: str = "none"  # provenance of the current snapshot: "csv" | "datastore"
_ts: float = 0.0  # time.time() when published (wall clock, for status/debug)


def publish(tables: dict[str, pd.DataFrame], source: str, ts: float) -> None:
    """Atomically replace the served snapshot with a new set of tables."""
    global _tables, _source, _ts
    snapshot = dict(tables)  # shallow copy of the mapping; frames are shared
    with _lock:
        _tables = snapshot
        _source = source
        _ts = ts


def is_ready() -> bool:
    """True once any snapshot (CSV bootstrap or Data Store) has been published."""
    with _lock:
        return _tables is not None


def has_table(name: str) -> bool:
    with _lock:
        return _tables is not None and name in _tables


def get_table(name: str) -> pd.DataFrame:
    """Return a copy of one published table (callers may mutate it freely)."""
    with _lock:
        if _tables is None or name not in _tables:
            raise KeyError(name)
        return _tables[name].copy()


def status() -> dict:
    """Snapshot provenance for /health/snapshot and logs (no row data)."""
    with _lock:
        return {
            "ready": _tables is not None,
            "source": _source,
            "tables": len(_tables) if _tables is not None else 0,
            "published_at": _ts,
        }


def clear() -> None:
    """Drop the snapshot (test/ops hook). Next read falls back to the source."""
    global _tables, _source, _ts
    with _lock:
        _tables = None
        _source = "none"
        _ts = 0.0
