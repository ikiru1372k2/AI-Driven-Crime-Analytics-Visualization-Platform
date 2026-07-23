/**
 * The Risk Ladder — the FORECAST tab's signature element.
 *
 * One ranked bullet bar per district, read top-to-bottom. The bar length is the
 * QuickML forecast (expected_count); a tick marks today's baseline
 * (recent_count), so the GAP between them is the momentum — visible before you
 * read a single number. risk_level is a status encoding: it drives the reserved
 * status colour AND a text chip + sorted rank, never colour alone. Rows are
 * buttons; clicking one expands the district's detail (summary, drivers,
 * confidence, sample FIRs) in place.
 *
 * Every displayed number is QuickML's or computed from it — nothing invented.
 */
import type { RiskDistrict } from "../lib/api";

export type LadderFilter = "all" | "high" | "rising";

interface Props {
  districts: RiskDistrict[];
  filter: LadderFilter;
  onFilterChange: (f: LadderFilter) => void;
  expandedId: string | null;
  onToggle: (districtId: string) => void;
  onOpenCase: (caseId: string) => void;
  windowDays: number;
}

const FILTERS: { key: LadderFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "high", label: "High risk" },
  { key: "rising", label: "Rising" },
];

function trendGlyph(t: string): string {
  return t === "up" ? "▲" : t === "down" ? "▼" : "▬";
}

export function RiskLadder({
  districts,
  filter,
  onFilterChange,
  expandedId,
  onToggle,
  onOpenCase,
  windowDays,
}: Props) {
  // One scale across the FULL set so bars don't rescale when a filter narrows
  // the list — a district's bar means the same thing in every view.
  const maxVal = Math.max(1, ...districts.map((d) => Math.max(d.expected_count, d.recent_count)));

  const shown = districts
    .filter((d) =>
      filter === "high" ? d.risk_level === "High" : filter === "rising" ? d.trend === "up" : true,
    )
    .sort((a, b) => b.expected_count - a.expected_count);

  return (
    <section className="fc-ladder" aria-label="Risk ladder">
      <div className="fc-ladder-head">
        <h2 className="fc-ladder-title">Risk ladder</h2>
        <div className="fc-filter" role="group" aria-label="Filter districts">
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

      <p className="fc-ladder-key">
        Bar length is the forecast; the marker <i className="fc-tick-legend" aria-hidden /> is cases
        now — the gap is the momentum.
      </p>

      {shown.length === 0 ? (
        <p className="muted small fc-ladder-empty">No districts match this filter.</p>
      ) : (
        <ul className="fc-rungs">
          {shown.map((d) => {
            const open = expandedId === d.district_id;
            const fillPct = (d.expected_count / maxVal) * 100;
            const tickPct = (d.recent_count / maxVal) * 100;
            const pct = d.forecast_pct_change;
            const lvl = d.risk_level.toLowerCase();
            const llm = d.summary_source !== "template";
            return (
              <li
                key={d.district_id}
                id={"rl-" + d.district_id}
                className={"fc-rung-wrap" + (open ? " is-open" : "")}
              >
                <button
                  className="fc-rung"
                  aria-expanded={open}
                  onClick={() => onToggle(d.district_id)}
                  title={`Forecast ${d.expected_count} cases · ${d.recent_count} now · ${
                    pct > 0 ? "+" : ""
                  }${pct}%`}
                >
                  <span className="fc-rung-name">{d.district_name}</span>
                  <span className="fc-track">
                    <span
                      className={"fc-fill level-" + lvl}
                      style={{ width: fillPct + "%" }}
                      aria-hidden
                    />
                    <span className="fc-tick" style={{ left: tickPct + "%" }} aria-hidden />
                  </span>
                  <span className="fc-rung-num">{d.expected_count}</span>
                  <span className={"fc-rung-pct trend-" + d.trend}>
                    {trendGlyph(d.trend)} {Math.abs(pct)}%
                  </span>
                  <span className={"fc-chip level-" + lvl}>{d.risk_level}</span>
                  <span className={"fc-caret" + (open ? " is-open" : "")} aria-hidden>
                    ▸
                  </span>
                </button>

                {open && (
                  <div className="fc-detail">
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
                    <div className="fc-detail-foot">
                      <span
                        className={"fc-conf conf-" + d.confidence.level}
                        title={d.confidence.basis}
                      >
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
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <p className="fc-ladder-note muted small">
        Numbers are model predictions for the next {windowDays} days — a planning guide, not a
        certainty.
      </p>
    </section>
  );
}
