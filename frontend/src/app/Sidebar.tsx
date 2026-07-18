/**
 * Control + insight rail. Crime-type and recency filters drive both queries;
 * stat tiles summarise the current view; the ranked hotspot list is the entry
 * point into the map detail panel.
 */
import type { Filters, Hotspot, Meta } from "../lib/api";

const DAY_PRESETS: { label: string; days: number | null }[] = [
  { label: "All", days: null },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "180d", days: 180 },
];

interface Props {
  meta: Meta | null;
  filters: Filters;
  onFilters: (f: Filters) => void;
  caseCount: number;
  hotspots: Hotspot[];
  alertStationIds: Set<string>;
  selectedRank: number | null;
  onSelectHotspot: (h: Hotspot | null) => void;
  loading: boolean;
}

export function Sidebar({
  meta,
  filters,
  onFilters,
  caseCount,
  hotspots,
  alertStationIds,
  selectedRank,
  onSelectHotspot,
  loading,
}: Props) {
  const topCount = hotspots[0]?.case_count ?? 0;

  return (
    <div className="sidebar">
      <div className="brand">
        <h1>KAVACH AI</h1>
        <p>Karnataka Crime Intelligence · Hotspot Map</p>
      </div>

      {/* filters */}
      <div>
        <p className="section-label">Scope · drill</p>
        <div className="field">
          <select
            value={filters.districtId ?? ""}
            onChange={(e) => onFilters({ ...filters, districtId: e.target.value || null })}
            aria-label="District filter"
          >
            <option value="">Karnataka (all districts)</option>
            {meta?.districts.map((d) => (
              <option key={d.district_id} value={d.district_id}>
                {d.district_name}
              </option>
            ))}
          </select>
        </div>

        <p className="section-label">Crime type</p>
        <div className="field">
          <select
            value={filters.subheadId ?? ""}
            onChange={(e) => onFilters({ ...filters, subheadId: e.target.value || null })}
            aria-label="Crime type filter"
          >
            <option value="">All crime types</option>
            {meta?.crime_subheads.map((s) => (
              <option key={s.subhead_id} value={s.subhead_id}>
                {s.subhead_name} ({s.head_name})
              </option>
            ))}
          </select>
        </div>

        <p className="section-label">Recency</p>
        <div className="chips">
          {DAY_PRESETS.map((p) => (
            <button
              key={p.label}
              className={"chip" + (filters.days === p.days ? " active" : "")}
              onClick={() => onFilters({ ...filters, days: p.days })}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* stats */}
      <div>
        <p className="section-label">Current view {loading ? "· loading…" : ""}</p>
        <div className="stats">
          <div className="tile">
            <div className="v">{caseCount.toLocaleString()}</div>
            <div className="k">Cases plotted</div>
          </div>
          <div className="tile accent">
            <div className="v">{hotspots.length}</div>
            <div className="k">Hotspots</div>
          </div>
          <div className="tile">
            <div className="v">{topCount}</div>
            <div className="k">Largest cluster</div>
          </div>
          <div className="tile">
            <div className="v">{meta ? meta.cases_with_coords.toLocaleString() : "—"}</div>
            <div className="k">Geolocated total</div>
          </div>
        </div>
      </div>

      {/* hotspot list */}
      <div>
        <p className="section-label">Detected hotspots (ranked)</p>
        {hotspots.length === 0 && !loading && (
          <div className="empty">No clusters for this filter. Try a wider recency or “All”.</div>
        )}
        <div className="hotspot-list">
          {hotspots.map((h) => (
            <button
              key={h.rank}
              className={"hotspot-row" + (h.rank === selectedRank ? " selected" : "")}
              onClick={() => onSelectHotspot(h.rank === selectedRank ? null : h)}
            >
              <span className="rank">#{h.rank}</span>
              <span>
                <div className="name">
                  {h.station_name ?? h.top_crime ?? "Hotspot"}
                  {h.station_id && alertStationIds.has(h.station_id) && (
                    <span className="pulse-tag" title="Active trend alert here">● alert</span>
                  )}
                </div>
                <div className="meta">
                  {h.top_crime} · {Math.round(h.radius_m)} m ·{" "}
                  {(h.night_share * 100).toFixed(0)}% night
                </div>
              </span>
              <span className="count">{h.case_count}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
