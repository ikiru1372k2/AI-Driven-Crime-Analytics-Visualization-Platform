/**
 * The anomaly queue — the FLAG tab's signature element.
 *
 * One expandable row per flagged case, read top-to-bottom in severity/score
 * order. Severity is a status encoding: it drives the reserved status colour AND
 * a text chip AND the rank order — never colour alone. The "✓ ML" badge marks a
 * flag the IsolationForest independently agrees is an outlier. Expanding a row
 * reveals the human-checkable reason, which signals fired, when the case
 * happened, whether the sentence was model- or template-phrased, and buttons to
 * open the evidence FIRs in the network view.
 *
 * Every number shown is computed from source cases or the model's own score —
 * nothing invented.
 */
import type { AnomalyFlag } from "../lib/api";

export type FlagFilter = "all" | "critical" | "ml";

interface Props {
  flags: AnomalyFlag[];
  filter: FlagFilter;
  onFilterChange: (f: FlagFilter) => void;
  expandedId: string | null;
  onToggle: (caseId: string) => void;
  onOpenCase: (caseId: string) => void;
}

const FILTERS: { key: FlagFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "critical", label: "Critical" },
  { key: "ml", label: "ML-confirmed" },
];

const SIGNAL_LABEL: Record<string, string> = {
  many_accused: "unusually many accused",
  odd_hour: "unusual timing",
  rare_offence: "out-of-place offence",
};

export function AnomalyList({
  flags,
  filter,
  onFilterChange,
  expandedId,
  onToggle,
  onOpenCase,
}: Props) {
  // flags arrive ranked by score; filters only narrow, never reorder
  const shown = flags.filter((f) =>
    filter === "critical" ? f.severity === "critical" : filter === "ml" ? f.ml_confirmed : true,
  );

  return (
    <section className="fl-queue" aria-label="Anomaly queue">
      <div className="fl-queue-head">
        <h2 className="fl-queue-title">Review queue</h2>
        <div className="fc-filter" role="group" aria-label="Filter flags">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              className={"fc-filter-btn" + (filter === f.key ? " is-active" : "")}
              aria-pressed={filter === f.key}
              onClick={() => onFilterChange(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {shown.length === 0 ? (
        <p className="muted small fl-queue-empty">No flags match this filter.</p>
      ) : (
        <ul className="fl-flags">
          {shown.map((f) => {
            const open = expandedId === f.case_id;
            const llm = f.explanation_source !== "template";
            return (
              <li
                key={f.case_id}
                className={"fl-flag-wrap sev-" + f.severity + (open ? " is-open" : "")}
              >
                <button
                  className="fl-flag"
                  aria-expanded={open}
                  onClick={() => onToggle(f.case_id)}
                  title={`${f.title} — ${f.score.toFixed(1)}σ from normal`}
                >
                  <span className="fl-rank" aria-hidden>
                    {f.rank}
                  </span>
                  <span className={"fl-sev sev-" + f.severity}>{f.severity}</span>
                  <span className="fl-flag-main">
                    <span className="fl-flag-title">{f.title}</span>
                    <span className="fl-flag-where">
                      {f.subject.station_name} · {f.subject.district_name} ·{" "}
                      {f.subject.subhead_name}
                    </span>
                  </span>
                  {f.ml_confirmed && (
                    <span
                      className="fl-ml"
                      title="IsolationForest independently marks this case an outlier"
                    >
                      ✓ ML
                    </span>
                  )}
                  <span className="fl-score" title="Modified z-score of the headline signal">
                    {f.score.toFixed(1)}σ
                  </span>
                  <span className={"fl-caret" + (open ? " is-open" : "")} aria-hidden>
                    ▸
                  </span>
                </button>

                {open && (
                  <div className="fl-detail">
                    <p className="fl-reason">{f.reason}</p>
                    <div className="fl-signals" aria-label="Signals that fired">
                      {f.signals.map((s) => (
                        <span key={s} className="fl-signal">
                          {SIGNAL_LABEL[s] ?? s}
                        </span>
                      ))}
                    </div>
                    <div className="fl-detail-foot">
                      {f.when && <span className="fl-when">Case time: {f.when}</span>}
                      <span className="fl-source">
                        {llm ? `explained by ${f.explanation_source}` : "standard read-out"}
                      </span>
                    </div>
                    <div className="fl-cases">
                      <span className="fl-cases-label">Open FIR:</span>
                      {f.sample_case_ids.slice(0, 6).map((id) => (
                        <button
                          key={id}
                          className="fl-case-btn"
                          onClick={() => onOpenCase(id)}
                          title="Open this case in the network view"
                        >
                          FIR {id}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <p className="fl-queue-note muted small">
        Leads to review, not findings — each flag is a case to open and check. All data is synthetic.
      </p>
    </section>
  );
}
