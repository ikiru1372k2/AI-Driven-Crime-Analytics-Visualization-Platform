/**
 * Anomaly Detection (FLAG tab, C2-R10) — the platform's "what's out of place?" screen.
 *
 * Hotspots say WHERE crime concentrates, trends say WHAT is rising, the forecast
 * says HOW MANY next month. This tab answers the fourth question none of them do:
 * WHICH single case is strange — the FIR whose attributes are out of place for its
 * station and offence. It reads as a ranked review queue: each row a lead to open
 * and check, never a conclusion.
 *
 * Detection is transparent statistics (so every flag carries a human-checkable
 * reason), corroborated by a scikit-learn IsolationForest (the "✓ ML" badge), and
 * phrased by GLM-4.7 where available — fenced against inventing numbers, so the
 * sentence degrades to a deterministic template rather than a fabrication.
 *
 * This component is the orchestrator only — fetch, the honest states, the summary
 * strip and the provenance footer. The queue itself lives in AnomalyList so every
 * file stays well under the size gate. All data is SYNTHETIC (ADR-011).
 */
import { useState } from "react";
import { fetchAnomalies } from "../lib/api";
import { useCachedQuery } from "../lib/queryCache";
import { Loading } from "./Loading";
import { AnomalyList, type FlagFilter } from "./AnomalyList";

const REVALIDATE_MS = 5 * 60_000; // background reload cadence (backend TTL ~5 min)

interface Props {
  onOpenCase: (caseId: string) => void;
}

export function AnomaliesView({ onOpenCase }: Props) {
  // Cached at module scope: switching tabs and back reuses this instantly
  // instead of re-scanning (PERF-001). Reloads silently on an interval; the
  // Refresh button forces a live, blocking reload.
  const { data, error, refreshing, refresh } = useCachedQuery(
    "anomalies:30",
    () => fetchAnomalies(30),
    { refetchIntervalMs: REVALIDATE_MS },
  );
  const [filter, setFilter] = useState<FlagFilter>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (error) {
    return (
      <div className="fl-body">
        <div className="empty">Backend unreachable — {String(error)}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="fl-body">
        <Loading label="Scanning for anomalies" rows={6} />
      </div>
    );
  }

  const env = data.intelligence;
  const flags = data.flags;
  const tally = {
    critical: flags.filter((f) => f.severity === "critical").length,
    serious: flags.filter((f) => f.severity === "serious").length,
    warning: flags.filter((f) => f.severity === "warning").length,
    ml: flags.filter((f) => f.ml_confirmed).length,
  };
  const modelVersion = env?.method.model_version ?? data.model_version;
  const toggle = (id: string) => setExpandedId((cur) => (cur === id ? null : id));

  return (
    <div className="fl-body">
      <header className="fl-header">
        <div>
          <h1>Anomaly Detection</h1>
          <p className="fl-sub">
            Cases whose details are out of place for their station and offence — a ranked queue of
            leads to check, not conclusions. Every flag carries a plain-English reason you can
            verify, and a “✓ ML” badge where an unsupervised model agrees it’s an outlier.
          </p>
        </div>
        <div className="hdr-actions">
          {env && (
            <span className="badge" title={`Model: ${modelVersion}`}>
              {env.classification_label}
            </span>
          )}
          <button className="refresh-btn" onClick={refresh} disabled={refreshing}>
            ↻ {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </header>

      {flags.length === 0 ? (
        <div className="fl-clear">
          <strong>Nothing out of place.</strong>
          <p className="muted">
            No case in the last {data.params.window_days} days crossed the anomaly threshold. The
            scan runs on transparent statistics that always execute offline, so this is a genuine
            all-clear — not a failed call.
          </p>
        </div>
      ) : (
        <>
          <div className="fl-strip" role="group" aria-label="Flag summary">
            <span className="fl-strip-total">{flags.length}</span>
            <span className="fl-strip-total-l">flagged for review</span>
            <span className="fl-strip-sep" aria-hidden />
            <FlTally n={tally.critical} label="critical" cls="critical" />
            <FlTally n={tally.serious} label="serious" cls="serious" />
            <FlTally n={tally.warning} label="warning" cls="warning" />
            <span className="fl-strip-sep" aria-hidden />
            <span
              className="fl-strip-ml"
              title="Independently corroborated by the IsolationForest model"
            >
              ✓ {tally.ml} ML-confirmed
            </span>
          </div>

          <AnomalyList
            flags={flags}
            filter={filter}
            onFilterChange={setFilter}
            expandedId={expandedId}
            onToggle={toggle}
            onOpenCase={onOpenCase}
          />
        </>
      )}

      {env?.limitations && env.limitations.length > 0 && (
        <footer className="fl-foot">
          {env.limitations.map((l) => (
            <p key={l} className="muted small">
              {l}
            </p>
          ))}
          <p className="muted small">Model: {modelVersion}</p>
        </footer>
      )}
    </div>
  );
}

function FlTally({ n, label, cls }: { n: number; label: string; cls: string }) {
  return (
    <span className={"fl-tally sev-" + cls} data-empty={n === 0}>
      <span className="fl-tally-n">{n}</span> {label}
    </span>
  );
}
