/**
 * State Intelligence Overview (#62) + Alerts experience (#69).
 * Answers "what requires attention now?" — headline tallies, ranked emerging
 * trend alerts (each with evidence + sparkline + acknowledge action), and the
 * largest spatial hotspots as a bridge into the map view.
 */
import { useEffect, useState } from "react";
import { fetchOverview, type Overview as OverviewData, type Severity, type TrendAlert } from "../lib/api";
import { Sparkline } from "./Sparkline";

const SEV_COLOR: Record<string, string> = {
  critical: "#d03b3b",
  serious: "#ec835a",
  warning: "#fab219",
};

function sevColor(s: Severity): string {
  return s ? SEV_COLOR[s] : "#3987e5";
}

export function Overview({ onOpenMap }: { onOpenMap: () => void }) {
  const [data, setData] = useState<OverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [acked, setAcked] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchOverview().then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="overview"><div className="empty">Backend unreachable — {error}</div></div>;
  if (!data) return <div className="overview"><div className="empty">Loading intelligence summary…</div></div>;

  const alertKey = (a: TrendAlert) => `${a.station_id}-${a.subhead_id}`;
  const toggleAck = (a: TrendAlert) =>
    setAcked((prev) => {
      const next = new Set(prev);
      const k = alertKey(a);
      next.has(k) ? next.delete(k) : next.add(k);
      return next;
    });

  const t = data.alert_tally;

  return (
    <div className="overview">
      <div className="ov-head">
        <div>
          <h2>State Intelligence Overview</h2>
          <p className="sub">What requires attention now · {data.date_range.from} → {data.date_range.to}</p>
        </div>
      </div>

      {/* headline tiles */}
      <div className="ov-tiles">
        <div className="tile">
          <div className="v">{data.total_cases.toLocaleString()}</div>
          <div className="k">Total cases</div>
        </div>
        <div className="tile" style={{ borderLeft: `3px solid ${SEV_COLOR.critical}` }}>
          <div className="v" style={{ color: SEV_COLOR.critical }}>{t.critical}</div>
          <div className="k">Critical alerts</div>
        </div>
        <div className="tile" style={{ borderLeft: `3px solid ${SEV_COLOR.serious}` }}>
          <div className="v" style={{ color: SEV_COLOR.serious }}>{t.serious}</div>
          <div className="k">Serious alerts</div>
        </div>
        <div className="tile" style={{ borderLeft: `3px solid ${SEV_COLOR.warning}` }}>
          <div className="v" style={{ color: SEV_COLOR.warning }}>{t.warning}</div>
          <div className="k">Watch alerts</div>
        </div>
        <div className="tile">
          <div className="v">{data.hotspot_count}</div>
          <div className="k">Active hotspots</div>
        </div>
      </div>

      <div className="ov-grid">
        {/* emerging trends / alerts */}
        <section>
          <p className="section-label">Emerging trends · ranked by deviation</p>
          {data.top_trends.length === 0 && <div className="empty">No emerging trends detected.</div>}
          <div className="alert-list">
            {data.top_trends.map((a) => {
              const isAcked = acked.has(alertKey(a));
              return (
                <article key={alertKey(a)} className={"alert-card" + (isAcked ? " acked" : "")}>
                  <span className="sev-bar" style={{ background: sevColor(a.severity) }} />
                  <div className="alert-main">
                    <div className="alert-top">
                      <span className="sev-badge" style={{ color: sevColor(a.severity) }}>
                        ● {a.severity ?? "info"}
                      </span>
                      <span className="alert-title">
                        {a.subhead_name} rising{a.station_name ? ` at ${a.station_name}` : ""}
                      </span>
                    </div>
                    <div className="alert-metrics">
                      <span><b>{a.recent_count}</b> cases / {a.window.from.slice(5)}–{a.window.to.slice(5)}</span>
                      <span>baseline <b>{a.baseline_weekly_median}</b>/wk</span>
                      {a.pct_change != null && <span className="up">▲ {a.pct_change}%</span>}
                      <span className="z">z {a.z_score}</span>
                    </div>
                  </div>
                  <div className="alert-spark">
                    <Sparkline
                      series={a.weekly_series}
                      recentWeeks={2}
                      baselineMedian={a.baseline_weekly_median}
                      color={sevColor(a.severity)}
                    />
                    <button className="ack" onClick={() => toggleAck(a)}>
                      {isAcked ? "Acknowledged ✓" : "Acknowledge"}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>

        {/* top hotspots bridge */}
        <section>
          <p className="section-label">Largest hotspots (90d)</p>
          <div className="hotspot-list">
            {data.top_hotspots.map((h) => (
              <button key={h.rank} className="hotspot-row" onClick={onOpenMap}>
                <span className="rank">#{h.rank}</span>
                <span>
                  <div className="name">{h.station_name ?? h.top_crime}</div>
                  <div className="meta">{h.top_crime} · {Math.round(h.radius_m)} m · {(h.night_share * 100).toFixed(0)}% night</div>
                </span>
                <span className="count">{h.case_count}</span>
              </button>
            ))}
          </div>
          <button className="open-map" onClick={onOpenMap}>Open hotspot map →</button>
        </section>
      </div>
    </div>
  );
}
