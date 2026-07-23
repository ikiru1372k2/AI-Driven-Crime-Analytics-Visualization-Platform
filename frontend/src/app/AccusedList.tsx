/**
 * Ranked accused list for the Identities tab — persons ordered by how many
 * crimes they committed, 15 at a time. Backed by the cheap /accused/ranked
 * group-by (never the O(n^2) resolve path), so it loads instantly instead of
 * timing out. Each page is cached at module scope (PERF-001), so paging back and
 * forth is instant. Each row offers a "Find similar person" action handled by
 * the parent (which runs the live search behind the blocking modal).
 */
import { useState } from "react";
import { fetchRankedAccused, type RankedAccused } from "../lib/api";
import { useCachedQuery } from "../lib/queryCache";
import { Loading } from "./Loading";

const PAGE = 15;

export function AccusedList({ onFindSimilar }: { onFindSimilar: (p: RankedAccused) => void }) {
  const [offset, setOffset] = useState(0);
  const { data, error } = useCachedQuery(`accused:ranked:${offset}`, () =>
    fetchRankedAccused(PAGE, offset),
  );

  if (error) return <div className="empty">Backend unreachable — {String(error)}</div>;
  if (!data) return <Loading label="Loading accused" rows={8} />;

  const { total, accused } = data;
  const from = total === 0 ? 0 : offset + 1;
  const to = offset + accused.length;

  return (
    <div className="accused-wrap">
      <div className="accused-list">
        {accused.map((p, i) => (
          <div className="accused-row" key={`${p.name}-${p.age}-${p.gender}-${i}`}>
            <span className="rank">#{offset + i + 1}</span>
            <div className="accused-who">
              <span className="an">{p.name}</span>
              <span className="am">
                age {p.age ?? "?"} · {p.gender ?? "?"}
                {p.districts.length > 0 &&
                  ` · ${p.districts.slice(0, 2).join(", ")}${p.districts.length > 2 ? "…" : ""}`}
              </span>
            </div>
            <span className="crime-count" title="distinct cases (crimes committed)">
              <b>{p.case_count}</b> case{p.case_count === 1 ? "" : "s"}
            </span>
            <button className="find-similar-btn" onClick={() => onFindSimilar(p)}>
              Find similar person
            </button>
          </div>
        ))}
        {accused.length === 0 && <div className="empty">No accused persons in the dataset.</div>}
      </div>

      <div className="accused-pager">
        <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
          ← Prev
        </button>
        <span>
          {from.toLocaleString()}–{to.toLocaleString()} of {total.toLocaleString()}
        </span>
        <button disabled={to >= total} onClick={() => setOffset(offset + PAGE)}>
          Next →
        </button>
      </div>
    </div>
  );
}
