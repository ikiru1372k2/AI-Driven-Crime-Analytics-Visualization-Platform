/**
 * Tiny module-scoped query cache (PERF-001) — no dependency, no provider.
 *
 * The tabs render conditionally (`view === "flag" && <AnomaliesView/>`), so a
 * tab UNMOUNTS when you switch away and its `useState` data is destroyed —
 * every revisit re-hit the API, even for endpoints that hadn't changed. This
 * cache lives at module scope (outside React), so it survives unmount: a
 * revisited tab paints instantly from cache instead of showing its spinner and
 * re-fetching.
 *
 * Behaviour:
 *  - **cache-first**: a cached entry is returned immediately on mount.
 *  - **stale-while-revalidate**: if the entry is older than `staleMs`, the stale
 *    value is shown at once and a background refetch swaps in fresh data.
 *  - **in-flight dedupe**: concurrent callers for one key share a single fetch.
 *
 * Kept deliberderately small (well under the ≤600-line source gate) and free of
 * react-query/SWR so the bundle stays lean.
 */
import { useCallback, useEffect, useRef, useState } from "react";

interface Entry<T> {
  data?: T;
  error?: unknown;
  ts: number; // when `data` was last set (ms epoch); 0 = never
  promise?: Promise<void>; // in-flight fetch, for dedupe
  refreshing: boolean; // a MANUAL refresh is in flight (the blocking modal)
  listeners: Set<() => void>;
}

const store = new Map<string, Entry<unknown>>();

const DEFAULT_STALE_MS = 5 * 60_000; // 5 min — matches the backend snapshot TTL

function entryFor<T>(key: string): Entry<T> {
  let e = store.get(key) as Entry<T> | undefined;
  if (!e) {
    e = { ts: 0, refreshing: false, listeners: new Set() };
    store.set(key, e as Entry<unknown>);
  }
  return e;
}

function notify(e: Entry<unknown>): void {
  for (const l of e.listeners) l();
}

/** Cheap structural equality — the payloads here are small JSON trees, so a
 *  stringify compare is enough to tell "the backend returned the same thing"
 *  from a genuine change. Lets a background reload skip the re-render entirely. */
function sameData(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (a === undefined || b === undefined) return false;
  try {
    return JSON.stringify(a) === JSON.stringify(b);
  } catch {
    return false; // non-serialisable (shouldn't happen for API data) → treat as changed
  }
}

/** Kick off a fetch for `key` unless one is already running. Updates freshness
 *  every time, but only notifies listeners when the data actually CHANGED (or an
 *  error surfaced) — so an interval reload that returns identical data is silent. */
function revalidate<T>(key: string, fetcher: () => Promise<T>): Promise<void> {
  const e = entryFor<T>(key);
  if (e.promise) return e.promise;
  e.promise = fetcher()
    .then((data) => {
      const changed = !sameData(e.data, data);
      e.ts = Date.now();
      e.error = undefined;
      if (changed) {
        e.data = data;
        notify(e as Entry<unknown>);
      }
    })
    .catch((err) => {
      // Keep any prior data on error (stale-but-usable); expose the error too.
      e.error = err;
      notify(e as Entry<unknown>);
    })
    .finally(() => {
      e.promise = undefined;
    });
  return e.promise;
}

export interface CachedQuery<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean; // true only when there is no data yet AND a fetch is running
  refreshing: boolean; // a manual refresh() is running — drives the button's inline state
  refresh: () => Promise<void>; // force a live background reload now (the Refresh button)
}

/**
 * Subscribe a component to a cached query. Returns cached data instantly when
 * present; fetches (or revalidates when stale) otherwise.
 *
 * @param key      stable cache key (include any params, e.g. `identity:${id}`)
 * @param fetcher  zero-arg loader; identity may change between renders, only
 *                 `key` and `enabled` drive refetching.
 * @param opts.enabled  gate the query (e.g. don't fetch a detail until expanded)
 * @param opts.staleMs  age after which cached data is revalidated in background
 * @param opts.refetchIntervalMs  when set, also reload in the background on this
 *                 cadence while mounted; identical results update nothing (SWR).
 */
export function useCachedQuery<T>(
  key: string,
  fetcher: () => Promise<T>,
  opts: { enabled?: boolean; staleMs?: number; refetchIntervalMs?: number } = {},
): CachedQuery<T> {
  const { enabled = true, staleMs = DEFAULT_STALE_MS, refetchIntervalMs } = opts;
  const [, forceRender] = useState(0);

  // Keep the latest fetcher without making it part of the query identity — the
  // interval and refresh() must call the current closure, not a stale one.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    if (!enabled) return;
    const e = entryFor<T>(key);
    const rerender = () => forceRender((n) => n + 1);
    e.listeners.add(rerender);

    const isStale = e.ts === 0 || Date.now() - e.ts > staleMs;
    if (isStale && !e.promise) void revalidate(key, fetcherRef.current);

    // Background auto-reload: silent unless the payload actually changed.
    const timer = refetchIntervalMs
      ? setInterval(() => {
          if (!e.promise) void revalidate(key, fetcherRef.current);
        }, refetchIntervalMs)
      : undefined;

    return () => {
      e.listeners.delete(rerender);
      if (timer) clearInterval(timer);
    };
    // fetcher intentionally excluded: `key`/`enabled` are the identity of the query.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled, staleMs, refetchIntervalMs]);

  // Force a live reload now and flag it as manual so callers can block the UI.
  const refresh = useCallback(async () => {
    if (!enabled) return;
    const e = entryFor<T>(key);
    e.refreshing = true;
    notify(e as Entry<unknown>);
    try {
      await revalidate(key, fetcherRef.current);
    } finally {
      e.refreshing = false;
      notify(e as Entry<unknown>);
    }
    // fetcherRef is stable; key/enabled are the query identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled]);

  const e = entryFor<T>(key);
  return {
    data: e.data,
    error: e.error,
    loading: enabled && e.data === undefined && e.promise !== undefined,
    refreshing: e.refreshing,
    refresh,
  };
}

/**
 * Warm a cache key WITHOUT subscribing a component — call at app start so a later
 * tab switch paints from cache instead of showing its spinner. Fire-and-forget:
 * reuses an in-flight fetch if one is already running (dedupe) and is a no-op
 * when the entry is still fresh. Must use the SAME key + fetcher as the tab's
 * `useCachedQuery` for the warm entry to be reused.
 */
export function prefetchQuery<T>(
  key: string,
  fetcher: () => Promise<T>,
  staleMs: number = DEFAULT_STALE_MS,
): void {
  const e = entryFor<T>(key);
  const isStale = e.ts === 0 || Date.now() - e.ts > staleMs;
  if (isStale && !e.promise) void revalidate(key, fetcher);
}

/** Drop one key (or everything) — e.g. a manual refresh control. */
export function invalidateQuery(key?: string): void {
  if (key === undefined) {
    store.clear();
    return;
  }
  const e = store.get(key);
  if (e) {
    e.ts = 0;
    e.data = undefined;
    e.error = undefined;
  }
}
