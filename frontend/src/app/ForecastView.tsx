/**
 * Area Risk Forecast (FORECAST tab) — the platform's one PROACTIVE screen.
 *
 * The judges asked for prediction, not just history. This shows, per district,
 * how many cases are expected in the next window and how that compares to now —
 * organised for triage: a statewide hero band (ForecastHero) over a ranked
 * bullet-bar Risk Ladder (RiskLadder). Every number is Zoho QuickML's (live),
 * never ours; the sentence is either a deterministic template or a GLM rephrase
 * fenced against inventing numbers. When QuickML is not configured/reachable we
 * say so honestly and show NO numbers (ADR-006).
 *
 * This component is the orchestrator only — fetch, the three honest states
 * (error / loading / unavailable), and the provenance footer. The hero band and
 * ladder live in sibling components to keep every file well under the size gate.
 */
import { useState } from "react";
import { fetchRisk } from "../lib/api";
import { useCachedQuery } from "../lib/queryCache";
import { Loading } from "./Loading";
import { ForecastHero } from "./ForecastHero";
import { RiskLadder, type LadderFilter } from "./RiskLadder";

const REVALIDATE_MS = 5 * 60_000; // background reload cadence (backend TTL ~5 min)

interface Props {
  onOpenCase: (caseId: string) => void;
}

export function ForecastView({ onOpenCase }: Props) {
  // Cached at module scope so re-entering the tab reuses the last forecast
  // instead of re-calling the live QuickML path (PERF-001). Reloads silently on
  // an interval; the Refresh button forces a live, blocking reload.
  const { data, error, refreshing, refresh } = useCachedQuery(
    "risk:30",
    () => fetchRisk(30),
    { refetchIntervalMs: REVALIDATE_MS },
  );
  const [filter, setFilter] = useState<LadderFilter>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (error) {
    return (
      <div className="fc-body">
        <div className="empty">Backend unreachable — {String(error)}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="fc-body">
        <Loading label="Loading forecast" rows={6} />
      </div>
    );
  }

  const env = data.intelligence;

  // Honest unavailable state — no fabricated numbers (the whole point).
  if (!data.available) {
    return (
      <div className="fc-body">
        <header className="fc-header">
          <div>
            <h1>Area Risk Forecast</h1>
            <p className="fc-sub">
              Where crime is expected to rise over the next {data.window_days} days.
            </p>
          </div>
          <div className="hdr-actions">
            {env && <span className="badge">{env.classification_label}</span>}
            <button className="refresh-btn" onClick={refresh} disabled={refreshing}>
              ↻ {refreshing ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        </header>
        <div className="fc-unavailable">
          <strong>Forecast unavailable — prediction service not configured.</strong>
          <p>
            The live forecast is produced by a Zoho QuickML model. It is not reachable from this
            environment, so no predicted numbers are shown. This is expected on the local demo
            build; on the deployed platform the model returns per-district forecasts here.
          </p>
          {data.reason && <p className="muted small">Reason: {data.reason}</p>}
        </div>
      </div>
    );
  }

  const modelVersion = env?.method.model_version ?? data.model_version;

  // Watchlist / hero jump: surface the district in the ladder and scroll to it.
  const focus = (districtId: string) => {
    setFilter("all");
    setExpandedId(districtId);
    requestAnimationFrame(() => {
      document
        .getElementById("rl-" + districtId)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  };
  const toggle = (districtId: string) =>
    setExpandedId((cur) => (cur === districtId ? null : districtId));

  return (
    <div className="fc-body">
      <header className="fc-header">
        <div>
          <h1>Area Risk Forecast</h1>
          <p className="fc-sub">
            Where crime is expected to rise over the next {data.window_days} days, across all{" "}
            {data.districts.length} districts. Numbers are model predictions — a guide for planning,
            not a certainty.
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

      <ForecastHero districts={data.districts} windowDays={data.window_days} onFocus={focus} />

      <RiskLadder
        districts={data.districts}
        filter={filter}
        onFilterChange={setFilter}
        expandedId={expandedId}
        onToggle={toggle}
        onOpenCase={onOpenCase}
        windowDays={data.window_days}
      />

      {env?.limitations && env.limitations.length > 0 && (
        <footer className="fc-foot">
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
