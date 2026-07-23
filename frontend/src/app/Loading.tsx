/**
 * Loading affordances (PERF-001 UX). Shown while a view's cached query is
 * warming, in place of a bare line of text.
 *
 * `Loading` fills an empty view with a themed spinner + a caption and skeleton
 * rows that echo the shape of the list about to arrive, so a warming tab reads
 * as "arriving" rather than "stuck". `Spinner` is the small inline variant for
 * sections that load beneath already-rendered content (an expanded card, a
 * subgraph). Both respect `prefers-reduced-motion` via the stylesheet.
 */

interface LoadingProps {
  /** What is loading, e.g. "Scanning for anomalies" (a trailing … is added). */
  label: string;
  /** How many skeleton rows to preview — roughly the incoming list length. */
  rows?: number;
  /** Extra class on the wrapper (e.g. to match a view's padding container). */
  className?: string;
}

export function Loading({ label, rows = 5, className }: LoadingProps) {
  return (
    <div
      className={"kv-loading" + (className ? " " + className : "")}
      role="status"
      aria-live="polite"
    >
      <div className="kv-loading-head">
        <span className="kv-spinner" aria-hidden />
        <span>{label}…</span>
      </div>
      <div className="kv-skel-rows" aria-hidden>
        {Array.from({ length: rows }, (_, i) => (
          // stagger widths so the block reads as content, not a solid slab
          <div
            key={i}
            className="skeleton kv-skel-row"
            style={{ width: `${94 - (i % 3) * 8}%` }}
          />
        ))}
      </div>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="kv-inline-load" role="status">
      <span className="kv-spinner sm" aria-hidden />
      {label && <span>{label}</span>}
    </span>
  );
}
