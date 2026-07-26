/**
 * MO Profiles tab — same shape as Identities: a centered search over a paged
 * list, and opening a row swaps to a detail view with a Back button.
 *
 * Two things a user does here:
 *   - search MO profiles by keyword (FIR number or words in the narrative) and
 *     narrow by MO attribute (action / target / mobility), or
 *   - open a particular case to read its narrative and the modus operandi
 *     extracted from it, then jump to other cases committed the same way.
 *
 * The whole tab is gated on a one-time "setting up" build (the index is built
 * off the request path), so a cold backend shows progress instead of hanging.
 */
import { useEffect, useState, type FormEvent } from "react";
import {
  fetchMoCase,
  fetchMoProfiles,
  fetchMoStatus,
  fetchMoVocabulary,
  fetchRelated,
  MO_FIELDS,
  type MoCase,
  type MoListRow,
  type MoMatch,
} from "../lib/moApi";
import { useCachedQuery } from "../lib/queryCache";
import { Loading, Spinner } from "./Loading";

const PAGE_SIZE = 15;
const UNKNOWN = "UNKNOWN";

// Module scope so it survives the tab unmounting: once the backend index is
// ready in this session, revisiting the MO tab skips the setup modal entirely
// (the "check cache first on next load" behaviour) while still confirming in
// the background.
let moIndexReady = false;

/** The MO keywords shown on a list row, UNKNOWN attributes dropped. */
function moTags(p: MoListRow): string {
  const tags = [p.crime_action.value, p.target_type.value, p.mobility.value]
    .map(String)
    .filter((v) => v && v !== UNKNOWN);
  return tags.length ? tags.join(" · ") : "no MO detail in the narrative";
}

/** Narrative with the active attribute's source span highlighted. */
function Narrative({ text, span }: { text: string; span: [number, number] | null }) {
  if (!span || span[0] >= span[1] || span[1] > text.length) {
    return <p className="mo-narrative">{text}</p>;
  }
  return (
    <p className="mo-narrative">
      {text.slice(0, span[0])}
      <mark className="mo-span">{text.slice(span[0], span[1])}</mark>
      {text.slice(span[1])}
    </p>
  );
}

/** Poll /status until the corpus index is built, without ever blocking a load. */
function useMoReady(): { ready: boolean; status: string; error: string | null } {
  const [ready, setReady] = useState(moIndexReady);
  const [status, setStatus] = useState(moIndexReady ? "ready" : "building");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (moIndexReady) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const s = await fetchMoStatus();
        if (!alive) return;
        setStatus(s.status);
        setError(s.error ?? null);
        if (s.ready) {
          moIndexReady = true;
          setReady(true);
          return;
        }
      } catch (e) {
        if (!alive) return;
        setError(String(e));
      }
      timer = setTimeout(tick, 1500);
    };
    tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, []);

  return { ready, status, error };
}

/** First-load setup gate: the index is being built off the request path, so we
 *  show progress instead of hanging the page (which used to time out). */
function MoSetup({ status, error }: { status: string; error: string | null }) {
  return (
    <div className="mo-setup">
      <div className="mo-setup-card">
        {error ? (
          <>
            <h2>Couldn’t set up MO profiles</h2>
            <p className="muted">{error}</p>
            <button className="expand" onClick={() => window.location.reload()}>
              Retry
            </button>
          </>
        ) : (
          <>
            <div className="mo-setup-spinner" aria-hidden />
            <h2>Setting up MO profiles…</h2>
            <p className="muted">
              Reading each FIR narrative and extracting its modus operandi. This runs
              once — the next visit opens instantly.
            </p>
            <p className="mo-setup-status">
              {status === "building" ? "Extracting…" : status}
            </p>
          </>
        )}
      </div>
    </div>
  );
}

/** MO tab entry point: gate the console on the index being ready. */
export function MoView() {
  const { ready, status, error } = useMoReady();
  if (!ready) return <MoSetup status={status} error={error} />;
  return <MoConsole />;
}

function MoConsole() {
  // Filter vocabulary — cached so revisiting the tab is instant (PERF-001).
  const { data: vocab = null } = useCachedQuery("mo:vocab", fetchMoVocabulary);
  // Search is submit-based (like Identities): `term` is what's typed, `q` is
  // what's committed and actually drives the list.
  const [term, setTerm] = useState("");
  const [q, setQ] = useState("");
  const [action, setAction] = useState("");
  const [target, setTarget] = useState("");
  const [mobility, setMobility] = useState("");
  const [selected, setSelected] = useState<number | null>(null);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setQ(term.trim());
    setSelected(null);
  };
  const active = Boolean(q || action || target || mobility);
  const clearAll = () => {
    setTerm("");
    setQ("");
    setAction("");
    setTarget("");
    setMobility("");
    setSelected(null);
  };

  return (
    <div className="idx">
      <div className="idx-head">
        <h2>MO Profiles</h2>
        <p className="sub">
          Search how crimes were committed — by FIR number or keywords — or open a case
          to see its modus operandi and other cases committed the same way.
        </p>
        <form className="id-search" onSubmit={onSubmit} role="search">
          <input
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            placeholder="Search by FIR number or words in the narrative…"
            aria-label="Search MO profiles by keyword"
          />
          <button type="submit">Search</button>
        </form>
        {vocab && (
          <div className="mo-filter-row">
            <select
              value={action}
              aria-label="Filter by action"
              onChange={(e) => {
                setAction(e.target.value);
                setSelected(null);
              }}
            >
              <option value="">Any action</option>
              {vocab.crime_action.map((v) => (
                <option key={v} value={v}>
                  {v.replace(/_/g, " ")}
                </option>
              ))}
            </select>
            <select
              value={target}
              aria-label="Filter by target"
              onChange={(e) => {
                setTarget(e.target.value);
                setSelected(null);
              }}
            >
              <option value="">Any target</option>
              {vocab.target_type.map((v) => (
                <option key={v} value={v}>
                  {v.replace(/_/g, " ")}
                </option>
              ))}
            </select>
            <select
              value={mobility}
              aria-label="Filter by mobility"
              onChange={(e) => {
                setMobility(e.target.value);
                setSelected(null);
              }}
            >
              <option value="">Any mobility</option>
              {vocab.mobility.map((v) => (
                <option key={v} value={v}>
                  {v.replace(/_/g, " ")}
                </option>
              ))}
            </select>
            {active && (
              <button type="button" className="mo-clear" onClick={clearAll}>
                Clear
              </button>
            )}
          </div>
        )}
      </div>

      {selected != null ? (
        <MoCaseView caseId={selected} onBack={() => setSelected(null)} onOpen={setSelected} />
      ) : (
        <MoCaseList
          q={q}
          action={action}
          target={target}
          mobility={mobility}
          onOpen={setSelected}
        />
      )}
    </div>
  );
}

function MoCaseList({
  q,
  action,
  target,
  mobility,
  onOpen,
}: {
  q: string;
  action: string;
  target: string;
  mobility: string;
  onOpen: (id: number) => void;
}) {
  const [offset, setOffset] = useState(0);
  // a changed search resets to the first page
  useEffect(() => {
    setOffset(0);
  }, [q, action, target, mobility]);

  const key = `mo:list:${q}|${action}|${target}|${mobility}|${offset}`;
  const { data, error } = useCachedQuery(key, () =>
    fetchMoProfiles({ q, action, target, mobility, limit: PAGE_SIZE, offset }),
  );

  if (error) return <div className="empty">Backend unreachable — {String(error)}</div>;
  if (!data) return <Loading label="Loading cases" rows={8} />;

  const { total, profiles } = data;
  const active = Boolean(q || action || target || mobility);
  const from = total === 0 ? 0 : offset + 1;
  const to = offset + profiles.length;

  return (
    <div className="accused-wrap">
      <p className="sub mo-count">
        {total.toLocaleString()} case{total === 1 ? "" : "s"}
        {active ? " match your search" : ""}
      </p>
      <div className="accused-list">
        {profiles.map((p) => (
          <button className="accused-row mo-row" key={p.case_master_id} onClick={() => onOpen(p.case_master_id)}>
            <div className="accused-who">
              <span className="an">FIR {p.case_master_id}</span>
              <span className="am">{moTags(p)}</span>
            </div>
            <span className="mo-open-hint">Open →</span>
          </button>
        ))}
        {profiles.length === 0 && (
          <div className="empty">
            {active ? "No FIR matches this search." : "No cases in the dataset."}
          </div>
        )}
      </div>

      {total > PAGE_SIZE && (
        <div className="accused-pager">
          <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            ← Prev
          </button>
          <span>
            {from.toLocaleString()}–{to.toLocaleString()} of {total.toLocaleString()}
          </span>
          <button disabled={to >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>
            Next →
          </button>
        </div>
      )}
    </div>
  );
}

function MoCaseView({
  caseId,
  onBack,
  onOpen,
}: {
  caseId: number;
  onBack: () => void;
  onOpen: (id: number) => void;
}) {
  const [detail, setDetail] = useState<MoCase | null>(null);
  const [span, setSpan] = useState<[number, number] | null>(null);
  const [related, setRelated] = useState<MoMatch[] | null>(null);
  const [loadingRelated, setLoadingRelated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDetail(null);
    setSpan(null);
    setRelated(null);
    setError(null);
    fetchMoCase(caseId).then(setDetail).catch((e) => setError(String(e)));
  }, [caseId]);

  const showRelated = () => {
    setLoadingRelated(true);
    fetchRelated(caseId)
      .then((r) => setRelated(r.matches))
      .catch((e) => setError(String(e)))
      .finally(() => setLoadingRelated(false));
  };

  return (
    <div className="match-view mo-detail">
      <div className="match-head">
        <button className="back-btn" onClick={onBack}>
          ← Back to list
        </button>
        <div>
          <h2>FIR {caseId}</h2>
          <p className="sub">How this crime was committed</p>
        </div>
      </div>

      {error ? (
        <div className="empty">{error}</div>
      ) : !detail ? (
        <div style={{ padding: "2rem" }}>
          <Spinner label="loading case…" />
        </div>
      ) : (
        <div className="mo-detail-grid">
          <div className="mo-panel">
            <header className="mo-panel-head">
              <strong>Narrative</strong>
            </header>
            <Narrative text={detail.narrative} span={span} />
            <p className="muted small">Hover a value to highlight where it came from.</p>
          </div>

          <div className="mo-panel">
            <header className="mo-panel-head">
              <strong>How it was committed</strong>
            </header>
            <ul className="mo-attrs">
              {MO_FIELDS.map(({ key, label }) => {
                const attr = detail.profile[key] as {
                  value: string | number;
                  source_span?: [number, number] | null;
                };
                const isUnknown = attr.value === UNKNOWN;
                return (
                  <li
                    key={key}
                    className={"mo-attr" + (isUnknown ? " unknown" : "")}
                    onMouseEnter={() => setSpan(attr.source_span ?? null)}
                    onMouseLeave={() => setSpan(null)}
                    onFocus={() => setSpan(attr.source_span ?? null)}
                    onBlur={() => setSpan(null)}
                    tabIndex={0}
                  >
                    <span className="mo-attr-label">{label}</span>
                    <span className="mo-attr-value">{isUnknown ? "—" : String(attr.value)}</span>
                  </li>
                );
              })}
            </ul>
            <p className="muted small">A dash means the narrative didn’t say.</p>
            <button className="expand" onClick={showRelated} disabled={loadingRelated}>
              {loadingRelated ? "finding…" : "Show similar cases"}
            </button>
          </div>

          {related !== null && (
            <div className="mo-panel mo-similar">
              <header className="mo-panel-head">
                <strong>Similar cases ({related.length})</strong>
              </header>
              {related.length === 0 ? (
                <p className="muted small">No other case was committed in a similar enough way.</p>
              ) : (
                <ul className="mo-related">
                  {related.map((m) => (
                    <li key={m.case_master_id}>
                      <button className="mo-related-row" onClick={() => onOpen(m.case_master_id)}>
                        <span className="mo-rel-id">FIR {m.case_master_id}</span>
                        <span className="mo-rel-why">{m.explanation}</span>
                        <span className="mo-rel-score">{(m.score * 100).toFixed(0)}%</span>
                      </button>
                      <p className="mo-rel-preview">{m.narrative_preview}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
