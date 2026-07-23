/**
 * Shared results list for the Identities tab. Rendered identically whether the
 * matches came from a per-row "Find similar" (name + age + sex) or the top name
 * search (name only) — one component, one look. Presentational only: the parent
 * runs the search and passes results in. A Back button returns to the list.
 *
 * Every match is a LEAD, not a confirmed same-person link (attribute similarity,
 * ADR-003) — the copy and the contributing/contradictory signals make the "why"
 * checkable rather than asserting identity.
 */
import type { PersonMatch } from "../lib/api";

interface Props {
  query: { name: string; age?: number | null; sex?: string | null };
  matches: PersonMatch[];
  onBack: () => void;
}

export function MatchList({ query, matches, onBack }: Props) {
  const qualifiers = [
    query.age != null ? `age ~${query.age}` : null,
    query.sex ? `sex ${query.sex}` : null,
  ].filter(Boolean);

  return (
    <div className="match-view">
      <div className="match-head">
        <button className="back-btn" onClick={onBack}>← Back to list</button>
        <div>
          <h2>Possible matches for “{query.name}”</h2>
          <p className="sub">
            {matches.length === 0
              ? "No similar people found"
              : `${matches.length} possible ${matches.length === 1 ? "person" : "people"}`}
            {qualifiers.length ? ` · ${qualifiers.join(" · ")}` : " · by name"} · leads for review,
            not confirmed identities
          </p>
        </div>
      </div>

      {matches.length === 0 ? (
        <div className="empty">
          No accused person resembles “{query.name}”. Try a shorter or differently spelled name.
        </div>
      ) : (
        <div className="match-list">
          {matches.map((m, i) => (
            <MatchCard key={`${m.name}-${m.age}-${m.gender}-${i}`} m={m} />
          ))}
        </div>
      )}
    </div>
  );
}

function MatchCard({ m }: { m: PersonMatch }) {
  return (
    <article className="match-card">
      <div className="match-main">
        <div className="match-top">
          <span className="conf">{(m.confidence * 100).toFixed(0)}%</span>
          <span className="match-name">{m.name}</span>
        </div>
        <div className="match-facts">
          <span>age {m.age ?? "?"}</span>
          <span>{m.gender ?? "?"}</span>
          <span>{m.case_count} case{m.case_count === 1 ? "" : "s"}</span>
          {m.cross_district && <span className="cross">▲ {m.districts.length} districts</span>}
        </div>
        {m.districts.length > 0 && (
          <div className="match-districts">
            {m.districts.map((d) => (
              <span key={d} className="dchip">{d}</span>
            ))}
          </div>
        )}
      </div>
      <div className="match-signals">
        {m.contributing.map((t, j) => (
          <span className="tag ok" key={`c${j}`}>{t}</span>
        ))}
        {m.contradictory.map((t, j) => (
          <span className="tag bad" key={`x${j}`}>{t}</span>
        ))}
      </div>
    </article>
  );
}
