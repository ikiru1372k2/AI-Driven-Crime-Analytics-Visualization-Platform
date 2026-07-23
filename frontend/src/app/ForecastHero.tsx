/**
 * FORECAST hero band — the whole state's next window in one glance.
 *
 * A stat tile (not a chart) answers "how many, which way" at state level; a
 * segmented proportion bar shows the High/Med/Low share; a watchlist strip
 * surfaces the districts that are both High risk AND rising — the ones an
 * officer resources first. Every figure is derived from QuickML's per-district
 * numbers (sum / count) — no value is invented here.
 */
import type { RiskDistrict } from "../lib/api";

interface Props {
  districts: RiskDistrict[];
  windowDays: number;
  onFocus: (districtId: string) => void;
}

const LEVELS = ["High", "Medium", "Low"] as const;

export function ForecastHero({ districts, windowDays, onFocus }: Props) {
  const totalExpected = districts.reduce((s, d) => s + d.expected_count, 0);
  const totalRecent = districts.reduce((s, d) => s + d.recent_count, 0);
  const netPct =
    totalRecent > 0 ? Math.round(((totalExpected - totalRecent) / totalRecent) * 100) : 0;
  const rising = districts.filter((d) => d.trend === "up").length;
  const falling = districts.filter((d) => d.trend === "down").length;

  const counts: Record<string, number> = { High: 0, Medium: 0, Low: 0 };
  for (const d of districts) counts[d.risk_level] += 1;
  const total = districts.length || 1;

  const watch = districts
    .filter((d) => d.risk_level === "High" && d.trend === "up")
    .sort((a, b) => b.expected_count - a.expected_count);

  const netGlyph = netPct > 0 ? "▲" : netPct < 0 ? "▼" : "▬";
  const netClass = netPct > 0 ? "up" : netPct < 0 ? "down" : "flat";

  return (
    <section className="fc-hero" aria-label="Statewide forecast summary">
      <div className="fc-hero-stat">
        <span className="fc-hero-n">{totalExpected.toLocaleString()}</span>
        <span className="fc-hero-l">
          cases expected statewide
          <br />
          next {windowDays} days
        </span>
      </div>

      <div className={"fc-hero-net trend-" + netClass}>
        <span className="fc-hero-net-row">
          <span className="fc-hero-net-glyph" aria-hidden>
            {netGlyph}
          </span>
          <span className="fc-hero-net-pct">
            {netPct > 0 ? "+" : ""}
            {netPct}%
          </span>
        </span>
        <span className="fc-hero-net-l">vs the last {windowDays} days</span>
        <span className="fc-hero-flow">
          {rising} rising · {falling} falling
        </span>
      </div>

      <div className="fc-prop">
        <div
          className="fc-prop-bar"
          role="img"
          aria-label={`${counts.High} high, ${counts.Medium} medium, ${counts.Low} low risk districts`}
        >
          {LEVELS.map((lvl) =>
            counts[lvl] > 0 ? (
              <span
                key={lvl}
                className={"fc-prop-seg level-" + lvl.toLowerCase()}
                style={{ width: (counts[lvl] / total) * 100 + "%" }}
                title={`${counts[lvl]} ${lvl.toLowerCase()}`}
              />
            ) : null,
          )}
        </div>
        <div className="fc-prop-legend">
          {LEVELS.map((lvl) => (
            <span key={lvl} className="fc-prop-key">
              <i className={"fc-dot level-" + lvl.toLowerCase()} aria-hidden /> {counts[lvl]}{" "}
              {lvl.toLowerCase()}
            </span>
          ))}
          <span className="fc-prop-total">across {districts.length} districts</span>
        </div>
      </div>

      {watch.length > 0 && (
        <div className="fc-watch">
          <span className="fc-watch-title">Needs attention this month</span>
          <div className="fc-watch-items">
            {watch.map((d) => (
              <button
                key={d.district_id}
                className="fc-watch-item"
                onClick={() => onFocus(d.district_id)}
                title="Show this district in the risk ladder"
              >
                <span className="fc-watch-name">{d.district_name}</span>
                <span className="fc-watch-n">{d.expected_count}</span>
                <span className="fc-watch-pct">▲{Math.abs(d.forecast_pct_change)}%</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
