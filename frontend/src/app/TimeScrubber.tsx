/**
 * Spatiotemporal scrubber (design review 1g) — proves the claim live.
 * Playback steps the recency window from a year down to 30 days; every
 * step re-runs the real DBSCAN endpoint, so hotspot evolution on screen
 * is computed, not animated. Honest label shows the active window.
 */
import { useEffect, useRef, useState } from "react";
import type { Filters } from "../lib/api";

const STEPS = [365, 300, 240, 180, 150, 120, 90, 60, 30];

interface Props {
  filters: Filters;
  onFilters: (f: Filters) => void;
}

export function TimeScrubber({ filters, onFilters }: Props) {
  const [playing, setPlaying] = useState(false);
  const idx = useRef(0);

  useEffect(() => {
    if (!playing) return;
    idx.current = 0;
    const t = setInterval(() => {
      if (idx.current >= STEPS.length) {
        setPlaying(false);
        return;
      }
      onFilters({ ...filters, days: STEPS[idx.current] });
      idx.current += 1;
    }, 1400);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);

  const active = filters.days;

  return (
    <div className="scrubber" role="group" aria-label="Time window scrubber">
      <button
        className={"scrub-play" + (playing ? " on" : "")}
        onClick={() => setPlaying(!playing)}
        aria-label={playing ? "Stop playback" : "Play hotspot evolution"}
      >
        {playing ? "◼" : "▶"}
      </button>
      <div className="scrub-steps">
        {STEPS.map((d) => (
          <button
            key={d}
            className={"scrub-step" + (active === d ? " active" : "")}
            onClick={() => onFilters({ ...filters, days: d })}
          >
            {d >= 60 ? `${Math.round(d / 30)}mo` : `${d}d`}
          </button>
        ))}
        <button
          className={"scrub-step" + (active == null ? " active" : "")}
          onClick={() => onFilters({ ...filters, days: null })}
        >
          all
        </button>
      </div>
      <span className="scrub-label">
        {playing
          ? "recomputing DBSCAN per window…"
          : active
            ? `window: last ${active} days`
            : "window: full range"}
      </span>
    </div>
  );
}
