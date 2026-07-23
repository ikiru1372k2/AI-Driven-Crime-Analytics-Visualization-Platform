/**
 * Evidence & Provenance browser (design review 1h) — EXPLAIN module.
 *
 * Every result answers "how do you know?": pick any intelligence run
 * (left), read its method card — name, version, window, status — and walk
 * each output's evidence to the source FIRs (center); the decision/audit
 * feed (right) shows that human actions are attributable and persistent.
 */
import { useEffect, useState } from "react";
import {
  fetchActivity,
  fetchEvidenceRuns,
  fetchRunDetail,
  type RunDetail,
} from "../lib/evidenceApi";
import { useCachedQuery } from "../lib/queryCache";
import { Spinner } from "./Loading";

const TYPE_COLORS: Record<string, string> = {
  HOTSPOT: "var(--series-1, #3987e5)",
  TREND_ALERT: "#e57373",
  ASSOCIATION: "#a76fb9",
  IDENTITY_CANDIDATE: "#d9a13b",
  MO_PROFILE: "#d9a13b",
  ANOMALY: "#d95926",
  AREA_RISK: "#5aa9a3",
  MO_SIMILARITY: "#d9a13b",
};

interface Props {
  onOpenCase: (caseId: number) => void;
}

export function EvidenceView({ onOpenCase }: Props) {
  // Runs + activity cached at module scope so tab revisits are instant
  // (PERF-001); the run detail stays selection-driven (lazy) below.
  const { data: runsData, error: runsError } = useCachedQuery(
    "evidence:runs",
    fetchEvidenceRuns,
  );
  const { data: activityData } = useCachedQuery("evidence:activity", fetchActivity);
  const runs = runsData?.runs ?? [];
  const activity = activityData?.activity ?? [];
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Auto-select the first completed run once the list arrives.
  useEffect(() => {
    if (selected || !runsData) return;
    const first = runsData.runs.find((x) => x.status === "COMPLETED");
    if (first) setSelected(first.run_id);
  }, [runsData, selected]);

  useEffect(() => {
    if (!selected) return;
    fetchRunDetail(selected).then(setDetail).catch((e) => setError(String(e)));
  }, [selected]);

  return (
    <div className="evidence-body">
      {/* outputs / runs rail */}
      <aside className="ev-rail">
        <div className="brand">
          <h1>Evidence &amp; Provenance</h1>
          <p>EXPLAIN · every result answers "how do you know?"</p>
        </div>
        <p className="section-label">Intelligence runs</p>
        <ul className="ev-runs" aria-label="Intelligence runs">
          {runs.map((r) => (
            <li key={r.run_id}>
              <button
                className={"ev-run" + (selected === r.run_id ? " active" : "")}
                onClick={() => setSelected(r.run_id)}
              >
                <span
                  className="ev-type"
                  style={{ color: TYPE_COLORS[r.intelligence_type] ?? "var(--ink-2)" }}
                >
                  {r.intelligence_type}
                </span>
                <span className="ev-run-meta">
                  {r.method_name} v{r.method_version} · {r.record_count} results
                </span>
                <span className={"ev-status " + r.status.toLowerCase()}>{r.status}</span>
              </button>
            </li>
          ))}
          {runs.length === 0 && !error && !runsError && (
            <li><Spinner label="loading runs…" /></li>
          )}
        </ul>
        {Boolean(error || runsError) && (
          <p className="error">{String(error ?? runsError)}</p>
        )}
      </aside>

      {/* method card + evidence walk */}
      <section className="ev-main" aria-label="Method and evidence">
        {detail ? (
          <>
            <div className="ev-method-card">
              <header>
                <span
                  className="ev-type big"
                  style={{ color: TYPE_COLORS[detail.run.intelligence_type] ?? "inherit" }}
                >
                  {detail.run.intelligence_type}
                </span>
                <span className={"ev-status " + detail.run.status.toLowerCase()}>
                  {detail.run.status}
                </span>
              </header>
              <dl className="metric-grid">
                <dt>Method</dt>
                <dd>
                  <code>
                    {detail.run.method_name} v{detail.run.method_version}
                  </code>
                  {detail.run.model_version ? ` · model ${detail.run.model_version}` : ""}
                </dd>
                <dt>Run</dt>
                <dd>
                  <code>{detail.run.run_id.slice(0, 12)}…</code> ·{" "}
                  {new Date(detail.run.generated_at).toLocaleString()}
                </dd>
                <dt>Analysis window</dt>
                <dd>
                  {detail.run.window_from.slice(0, 10)} → {detail.run.window_to.slice(0, 10)}
                </dd>
                <dt>Results</dt>
                <dd>
                  {detail.run.record_count} · {detail.evidence_count} evidence rows
                  {detail.evidence_truncated > 0 && ` (showing first ${detail.evidence.length})`}
                </dd>
              </dl>
            </div>

            <p className="section-label">
              Evidence — output → factors → source FIRs
            </p>
            <ul className="ev-list">
              {detail.evidence.map((ev) => (
                <li key={ev.result_ref} className="ev-item">
                  <div className="ev-item-head">
                    <code className="ev-ref">{ev.result_ref}</code>
                    <span className="badge">{ev.classification}</span>
                  </div>
                  {ev.factors.length > 0 && (
                    <p className="ev-factors">
                      {ev.factors.map((f) => (
                        <span key={f.name} className="ev-factor">
                          {f.name} {f.direction === "DOWN" ? "▾" : "▴"}{" "}
                          {Math.abs(f.contribution).toFixed(2)}
                        </span>
                      ))}
                    </p>
                  )}
                  <div className="ev-firs">
                    {ev.evidence_case_ids.slice(0, 14).map((c) => (
                      <button key={c} className="fir-chip" onClick={() => onOpenCase(c)}>
                        FIR {c}
                      </button>
                    ))}
                    {ev.evidence_case_total > 14 && (
                      <span className="muted small">
                        and {ev.evidence_case_total - 14} more
                      </span>
                    )}
                  </div>
                  {ev.limitations.length > 0 && (
                    <p className="muted small">{ev.limitations.join(" · ")}</p>
                  )}
                </li>
              ))}
              {detail.evidence.length === 0 && (
                <li className="muted">no evidence rows for this run</li>
              )}
            </ul>
          </>
        ) : selected ? (
          <div style={{ padding: "2rem" }}>
            <Spinner label="loading evidence…" />
          </div>
        ) : (
          <p className="muted" style={{ padding: "2rem" }}>
            select a run to inspect its method and evidence
          </p>
        )}
      </section>

      {/* decision / audit trail */}
      <aside className="ev-audit" aria-label="Decision trail">
        <p className="section-label">Decision trail</p>
        <ul className="ev-activity">
          {activity.map((a, i) => (
            <li key={i}>
              <span
                className="node-dot"
                style={{
                  background:
                    a.decision === "CONFIRMED"
                      ? "#3c9a5f"
                      : a.decision === "REJECTED"
                        ? "#d03b3b"
                        : "var(--series-1, #3987e5)",
                }}
                aria-hidden
              />
              <span className="ev-act-text">{a.text}</span>
              <span className="ev-act-when">{a.when.slice(0, 16).replace("T", " ")}</span>
            </li>
          ))}
          {activity.length === 0 && (
            <li className="muted small">
              no decisions yet — acknowledge an alert or review an identity and it
              will appear here, and survive reload
            </li>
          )}
        </ul>
        <p className="muted small">
          Decisions are recorded through the append-only audit framework — state
          can change, history cannot.
        </p>
      </aside>
    </div>
  );
}
