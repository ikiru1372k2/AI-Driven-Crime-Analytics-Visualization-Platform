/**
 * Area Risk Forecast (FORECAST tab) — the platform's one PROACTIVE screen.
 *
 * The judges asked for prediction, not just history. This shows, per district,
 * how many cases are expected in the next window and how that compares to now —
 * in plain English a senior officer can read at a glance. Every number is Zoho
 * QuickML's (live), never ours; the sentence is either a deterministic template
 * or a Qwen rephrase fenced against inventing numbers. When QuickML is not
 * configured/reachable we say so honestly and show NO numbers (ADR-006).
 */
import { useEffect, useState } from "react";
import { fetchRisk, type RiskDistrict, type RiskResponse } from "../lib/api";

interface Props {
  onOpenCase: (caseId: string) => void;
}

const LEVEL_ORDER: Record<string, number> = { High: 0, Medium: 1, Low: 2 };

function trendGlyph(trend: string): { glyph: string; word: string } {
  if (trend === "up") return { glyph: "▲", word: "rising" };
  if (trend === "down") return { glyph: "▼", word: "falling" };
  return { glyph: "▬", word: "steady" };
}

/** Cross-district tally shown up top so an officer sees the shape at a glance. */
function tally(districts: RiskDistrict[]): { High: number; Medium: number; Low: number } {
  const t = { High: 0, Medium: 0, Low: 0 };
  for (const d of districts) t[d.risk_level] += 1;
  return t;
}

function DistrictCard({
  d,
  onOpenCase,
}: {
  d: RiskDistrict;
  onOpenCase: (caseId: string) => void;
}) {
  const { glyph, word } = trendGlyph(d.trend);
  const pct = d.forecast_pct_change;
  const pctLabel = pct > 0 ? `+${pct}%` : `${pct}%`;
  const llm = d.summary_source !== "template";
  return (
    <article className={"fc-card level-" + d.risk_level.toLowerCase()}>
      <div className="fc-card-head">
        <span className="fc-rank">#{d.rank}</span>
        <h3 className="fc-district">{d.district_name}</h3>
        <span className={"fc-chip level-" + d.risk_level.toLowerCase()}>
          {d.risk_level} risk
        </span>
      </div>

      <div className="fc-numbers">
        <div className="fc-expected">
          <span className="fc-expected-n">{d.expected_count}</span>
          <span className="fc-expected-l">cases expected</span>
        </div>
        <div className={"fc-trend trend-" + d.trend}>
          <span className="fc-trend-glyph" aria-hidden>
            {glyph}
          </span>
          <span className="fc-trend-word">
            {word} {pctLabel}
          </span>
          <span className="fc-trend-base">vs {d.recent_count} now</span>
        </div>
      </div>

      <p className="fc-summary">{d.summary}</p>

      {d.drivers.length > 0 && (
        <ul className="fc-drivers" aria-label="Why">
          {d.drivers.map((driver) => (
            <li key={driver} className="fc-driver">
              {driver}
            </li>
          ))}
        </ul>
      )}

      <div className="fc-card-foot">
        <span className={"fc-conf conf-" + d.confidence.level} title={d.confidence.basis}>
          Confidence: {d.confidence.level}
        </span>
        <span className="fc-source">
          {llm ? `explained by ${d.summary_source}` : "standard read-out"}
        </span>
      </div>

      {d.sample_case_ids.length > 0 && (
        <div className="fc-cases">
          <span className="fc-cases-label">Recent cases:</span>
          {d.sample_case_ids.slice(0, 6).map((id) => (
            <button
              key={id}
              className="fc-case-btn"
              onClick={() => onOpenCase(id)}
              title="Open this case in the network view"
            >
              FIR {id}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}

export function ForecastView({ onOpenCase }: Props) {
  const [data, setData] = useState<RiskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchRisk(30)
      .then((r) => !cancelled && setData(r))
      .catch((e) => !cancelled && setError(String(e)));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="fc-body">
        <div className="empty">Backend unreachable — {error}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="fc-body">
        <p className="muted" style={{ padding: "2rem" }}>
          Loading forecast…
        </p>
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
          {env && <span className="badge">{env.classification_label}</span>}
        </header>
        <div className="fc-unavailable">
          <strong>Forecast unavailable — prediction service not configured.</strong>
          <p>
            The live forecast is produced by a Zoho QuickML model. It is not reachable
            from this environment, so no predicted numbers are shown. This is expected on
            the local demo build; on the deployed platform the model returns per-district
            forecasts here.
          </p>
          {data.reason && <p className="muted small">Reason: {data.reason}</p>}
        </div>
      </div>
    );
  }

  const districts = [...data.districts].sort(
    (a, b) =>
      LEVEL_ORDER[a.risk_level] - LEVEL_ORDER[b.risk_level] ||
      b.expected_count - a.expected_count,
  );
  const t = tally(districts);
  const modelVersion = env?.method.model_version ?? data.model_version;

  return (
    <div className="fc-body">
      <header className="fc-header">
        <div>
          <h1>Area Risk Forecast</h1>
          <p className="fc-sub">
            Where crime is expected to rise over the next {data.window_days} days, across
            all {districts.length} districts. Numbers are model predictions — a guide for
            planning, not a certainty.
          </p>
        </div>
        {env && (
          <span className="badge" title={`Model: ${modelVersion}`}>
            {env.classification_label}
          </span>
        )}
      </header>

      <div className="fc-tally">
        <span className="fc-tally-item level-high">{t.High} high risk</span>
        <span className="fc-tally-item level-medium">{t.Medium} medium</span>
        <span className="fc-tally-item level-low">{t.Low} low</span>
      </div>

      <div className="fc-grid">
        {districts.map((d) => (
          <DistrictCard key={d.district_id} d={d} onOpenCase={onOpenCase} />
        ))}
      </div>

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
