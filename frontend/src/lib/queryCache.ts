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
import { useEffect, useState } from "react";

interface Entry<T> {
  data?: T;
  error?: unknown;
  ts: number; // when `data` was last set (ms epoch); 0 = never
  promise?: Promise<void>; // in-flight fetch, for dedupe
  listeners: Set<() => void>;
}

const store = new Map<string, Entry<unknown>>();

const DEFAULT_STALE_MS = 5 * 60_000; // 5 min — matches the backend snapshot TTL

function entryFor<T>(key: string): Entry<T> {
  let e = store.get(key) as Entry<T> | undefined;
  if (!e) {
    e = { ts: 0, listeners: new Set() };
    store.set(key, e as Entry<unknown>);
  }
  return e;
}

function notify(e: Entry<unknown>): void {
  for (const l of e.listeners) l();
}

/** Kick off a fetch for `key` unless one is already running. */
function revalidate<T>(key: string, fetcher: () => Promise<T>): Promise<void> {
  const e = entryFor<T>(key);
  if (e.promise) return e.promise;
  e.promise = fetcher()
    .then((data) => {
      e.data = data;
      e.error = undefined;
      e.ts = Date.now();
    })
    .catch((err) => {
      // Keep any prior data on error (stale-but-usable); expose the error too.
      e.error = err;
    })
    .finally(() => {
      e.promise = undefined;
      notify(e as Entry<unknown>);
    });
  return e.promise;
}

export interface CachedQuery<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean; // true only when there is no data yet AND a fetch is running
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
 */
export function useCachedQuery<T>(
  key: string,
  fetcher: () => Promise<T>,
  opts: { enabled?: boolean; staleMs?: number } = {},
): CachedQuery<T> {
  const { enabled = true, staleMs = DEFAULT_STALE_MS } = opts;
  const [, forceRender] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    const e = entryFor<T>(key);
    const rerender = () => forceRender((n) => n + 1);
    e.listeners.add(rerender);

    const isStale = e.ts === 0 || Date.now() - e.ts > staleMs;
    if (isStale && !e.promise) void revalidate(key, fetcher);

    return () => {
      e.listeners.delete(rerender);
    };
    // fetcher intentionally excluded: `key`/`enabled` are the identity of the query.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled, staleMs]);

  const e = entryFor<T>(key);
  return {
    data: e.data,
    error: e.error,
    loading: enabled && e.data === undefined && e.promise !== undefined,
  };
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
