"""A tiny time-boxed memoizer for zero-argument builders (CAT-002 / PR-B).

The CSV adapter caches for the process lifetime because the dataset is static.
The Data Store adapter must instead let *console edits show up*, so its caches
expire after a short TTL and re-read. This helper unifies both: pass a ``ttl_fn``
that returns ``float("inf")`` for the static case and a finite number of seconds
for the live case, and the same call site works either way.

Only ``maxsize=1`` / no-argument builders are supported — that is all the data
adapters need, and it keeps the cache-key logic (there is none) trivial.
"""

from __future__ import annotations

import functools
import threading
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def timed_cache(ttl_fn: Callable[[], float]):
    """Memoize a zero-arg function, re-computing once its value is older than TTL.

    ``ttl_fn`` is consulted on every call, so the TTL can follow runtime config
    (e.g. switch between infinite for CSV and finite for the Data Store) without
    rebuilding the wrapper. ``float("inf")`` means "cache forever". A TTL of 0
    forces a re-compute on every call. The wrapper exposes ``cache_clear()``.
    """

    def decorator(fn: Callable[[], T]) -> Callable[[], T]:
        state: dict[str, object] = {"value": None, "ts": 0.0, "set": False}
        lock = threading.Lock()

        @functools.wraps(fn)
        def wrapper() -> T:
            ttl = ttl_fn()
            now = time.monotonic()
            with lock:
                fresh = state["set"] and (
                    ttl == float("inf") or now - float(state["ts"]) < ttl
                )
                if fresh:
                    return state["value"]  # type: ignore[return-value]
            # Compute outside the lock so a slow network read does not block
            # other callers; a rare double-compute under a cold burst is fine.
            value = fn()
            with lock:
                state["value"], state["ts"], state["set"] = value, now, True
            return value

        def cache_clear() -> None:
            with lock:
                state["set"] = False
                state["value"] = None

        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        return wrapper

    return decorator


def timed_cache_keyed(ttl_fn: Callable[[], float]):
    """``timed_cache`` for functions memoized per positional-argument key.

    Same TTL semantics as :func:`timed_cache`, but keeps one entry per distinct
    args tuple (all args must be hashable). Used for analytics whose result is
    a pure function of a few request parameters (e.g. the anomaly scan / risk
    forecast per ``window_days``) — so repeat requests and the background warmer
    reuse the same computed result. Exposes ``cache_clear()``.
    """

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        store: dict[tuple, tuple[object, float]] = {}
        lock = threading.Lock()

        @functools.wraps(fn)
        def wrapper(*args) -> T:
            ttl = ttl_fn()
            now = time.monotonic()
            with lock:
                hit = store.get(args)
                if hit is not None and (ttl == float("inf") or now - hit[1] < ttl):
                    return hit[0]  # type: ignore[return-value]
            value = fn(*args)
            with lock:
                store[args] = (value, now)
            return value

        def cache_clear() -> None:
            with lock:
                store.clear()

        wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
        return wrapper

    return decorator
