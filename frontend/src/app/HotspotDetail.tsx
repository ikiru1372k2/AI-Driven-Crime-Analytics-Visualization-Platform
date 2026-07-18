/**
 * Hotspot inspector — the spatiotemporal "money shot". Shows a hotspot's key
 * evidence plus a 24-bin time-of-day histogram, with the night window
 * (21:00–02:00) highlighted so a spike there is unmistakable.
 */
import type { Hotspot } from "../lib/api";

const NIGHT_HOURS = new Set([21, 22, 23, 0, 1, 2]);

export function HotspotDetail({ hotspot, onClose }: { hotspot: Hotspot; onClose: () => void }) {
  const hist = hotspot.hour_histogram;
  const maxH = Math.max(1, ...hist);
  const breakdown = Object.entries(hotspot.crime_breakdown).sort((a, b) => b[1] - a[1]);

  return (
    <aside className="detail" aria-label="Hotspot detail">
      <button className="close" onClick={onClose} aria-label="Close">
        ×
      </button>
      <h3>
        #{hotspot.rank} {hotspot.station_name ?? "Hotspot"}
      </h3>
      <p className="sub">
        {hotspot.district_name ?? ""} · top crime: {hotspot.top_crime ?? "—"}
      </p>

      <div className="kv">
        <span className="k">Cases in cluster</span>
        <span className="v">{hotspot.case_count}</span>
        <span className="k">Radius</span>
        <span className="v">{Math.round(hotspot.radius_m)} m</span>
        <span className="k">Night share (21:00–02:00)</span>
        <span className={"v" + (hotspot.night_share >= 0.6 ? " warn" : "")}>
          {(hotspot.night_share * 100).toFixed(0)}%
        </span>
      </div>

      <div className="hist">
        <div className="section-label">Incidents by hour of day</div>
        <div className="hist-legend">
          <span className="item">
            <span className="sw" style={{ background: "#3987e5" }} /> Day
          </span>
          <span className="item">
            <span className="sw" style={{ background: "#d95926" }} /> Night (21:00–02:00)
          </span>
        </div>
        <div className="bars" role="img" aria-label="Time-of-day histogram of incidents">
          {hist.map((count, hour) => (
            <div
              key={hour}
              className={"bar" + (NIGHT_HOURS.has(hour) ? " night" : "")}
              style={{ height: `${(count / maxH) * 100}%` }}
              title={`${String(hour).padStart(2, "0")}:00 — ${count} case${count === 1 ? "" : "s"}`}
            />
          ))}
        </div>
        <div className="hist-axis">
          <span>00</span>
          <span>06</span>
          <span>12</span>
          <span>18</span>
          <span>23</span>
        </div>
      </div>

      {breakdown.length > 0 && (
        <div className="breakdown">
          <div className="section-label">Crime breakdown</div>
          {breakdown.map(([name, n]) => (
            <div className="brow" key={name}>
              <span>{name}</span>
              <span className="n">{n}</span>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
