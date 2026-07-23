/**
 * Identities tab (redesigned). Replaces the all-at-once cluster review that
 * called the O(n^2) resolve path and timed out. Instead:
 *
 *   - a ranked list of accused (most crimes first, paged 15 at a time), and
 *   - on-demand similarity search, run ONE person at a time — either the top
 *     name search (name only) or a row's "Find similar" (name + age + sex).
 *
 * Both searches share one live call, one blocking "searching…" modal, and one
 * results component (MatchList). Matches are leads for review, not confirmed
 * identities (attribute similarity only, ADR-003).
 */
import { useState, type FormEvent } from "react";
import { fetchSimilarPersons, type PersonMatch, type RankedAccused } from "../lib/api";
import { AccusedList } from "./AccusedList";
import { MatchList } from "./MatchList";
import { SearchingModal } from "./SearchingModal";

interface Results {
  query: { name: string; age?: number | null; sex?: string | null };
  matches: PersonMatch[];
}

export function IdentityExplorer() {
  const [term, setTerm] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<Results | null>(null);
  const [error, setError] = useState<string | null>(null);

  // One live search path for both entry points. The modal blocks the UI while
  // the round-trip runs; results (or an empty set on failure) then replace the
  // list until the user goes Back.
  const runSearch = async (q: { name: string; age?: number | null; sex?: string | null }) => {
    const name = q.name.trim();
    if (!name || searching) return;
    setSearching(true);
    setError(null);
    try {
      const res = await fetchSimilarPersons({ ...q, name });
      setResults({ query: res.query, matches: res.matches });
    } catch (e) {
      setError(String(e));
      setResults({ query: { name, age: q.age ?? null, sex: q.sex ?? null }, matches: [] });
    } finally {
      setSearching(false);
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    runSearch({ name: term }); // top search: name only, any age/sex
  };
  const onFindSimilar = (p: RankedAccused) =>
    runSearch({ name: p.name, age: p.age, sex: p.gender }); // row: name + age + sex

  return (
    <div className="idx">
      <div className="idx-head">
        <h2>Identities</h2>
        <p className="sub">
          Accused ranked by how many crimes they committed. Search a name, or find people similar to
          any person — every match is a lead for review, never a confirmed identity.
        </p>
        <form className="id-search" onSubmit={onSubmit} role="search">
          <input
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            placeholder="Search a person by name…"
            aria-label="Search a person by name"
          />
          <button type="submit" disabled={!term.trim() || searching}>
            Search
          </button>
        </form>
      </div>

      {error && !searching && !results?.matches.length && (
        <div className="empty">Search failed — {error}</div>
      )}

      {results ? (
        <MatchList query={results.query} matches={results.matches} onBack={() => setResults(null)} />
      ) : (
        <AccusedList onFindSimilar={onFindSimilar} />
      )}

      <SearchingModal show={searching} />
    </div>
  );
}
