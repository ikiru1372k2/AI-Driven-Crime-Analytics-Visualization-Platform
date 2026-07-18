/**
 * KAVACH AI — interactive crime hotspot console (Phase 3).
 * Loads dataset meta, then drives the /cases and /hotspots endpoints from a
 * shared filter (crime type + recency). All data is SYNTHETIC (ADR-011) — the
 * persistent banner makes that explicit.
 */
import { useCallback, useEffect, useState } from "react";
import {
  fetchCases,
  fetchDistricts,
  fetchHotspots,
  fetchMeta,
  fetchTrends,
  type CaseRecord,
  type DistrictStat,
  type Filters,
  type Hotspot,
  type Meta,
  type TrendAlert,
} from "../lib/api";
import { MapView } from "./MapView";
import { Sidebar } from "./Sidebar";
import { HotspotDetail } from "./HotspotDetail";
import { Overview } from "./Overview";
import { readHashState, writeHashState } from "../lib/urlstate";
import "./styles.css";

const DEFAULT_FILTERS: Filters = { subheadId: null, districtId: null, days: null };

type View = "overview" | "map";

export function App() {
  const initial = readHashState();
  const [view, setView] = useState<View>(initial.view);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [filters, setFilters] = useState<Filters>({ ...DEFAULT_FILTERS, ...initial.filters });
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [alerts, setAlerts] = useState<TrendAlert[]>([]);
  const [districtStats, setDistrictStats] = useState<DistrictStat[]>([]);
  const [selectedRank, setSelectedRank] = useState<number | null>(initial.hotspot);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // load dataset meta + district velocity once (static for a demo run)
  useEffect(() => {
    fetchMeta().then(setMeta).catch((e) => setError(String(e)));
    fetchDistricts().then((d) => setDistrictStats(d.districts)).catch(() => {});
  }, []);

  // (re)query cases + hotspots + active alerts whenever filters change
  useEffect(() => {
    if (!meta) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const latest = meta.date_range.to;
    Promise.all([fetchCases(filters, latest), fetchHotspots(filters), fetchTrends(filters)])
      .then(([c, h, t]) => {
        if (cancelled) return;
        setCases(c.cases);
        setHotspots(h.hotspots);
        setAlerts(t.alerts);
      })
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [meta, filters]);

  // keep the URL hash in sync so any view is shareable / reloadable
  useEffect(() => {
    writeHashState({ view, filters, hotspot: selectedRank });
  }, [view, filters, selectedRank]);

  // changing a filter invalidates the current hotspot selection
  const onFilters = useCallback((f: Filters) => {
    setFilters(f);
    setSelectedRank(null);
  }, []);

  const onSelectHotspot = useCallback((h: Hotspot | null) => {
    setSelectedRank(h ? h.rank : null);
  }, []);

  // stations with an ACTIVE trend alert — the map pulses only these (never otherwise)
  const alertStationIds = new Set(
    alerts.map((a) => a.station_id).filter((s): s is string => s != null),
  );

  const selected = hotspots.find((h) => h.rank === selectedRank) ?? null;
  const center = meta?.map_center ?? { lat: 12.97, lon: 77.59 };

  return (
    <div className="app">
      <header className="banner">
        <span className="dot" />
        Synthetic demo data — not real FIRs
        <span className="sub">
          {meta
            ? `${meta.total_cases.toLocaleString()} cases · ${meta.date_range.from} → ${meta.date_range.to}`
            : "loading dataset…"}
        </span>
      </header>

      <nav className="tabs">
        <span className="tab-brand">KAVACH AI</span>
        <button className={"tab" + (view === "overview" ? " active" : "")} onClick={() => setView("overview")}>
          Overview
        </button>
        <button className={"tab" + (view === "map" ? " active" : "")} onClick={() => setView("map")}>
          Hotspot Map
        </button>
      </nav>

      {view === "overview" && <Overview onOpenMap={() => setView("map")} />}

      {view === "map" && (
      <div className="body">
        <Sidebar
          meta={meta}
          filters={filters}
          onFilters={onFilters}
          caseCount={cases.length}
          hotspots={hotspots}
          alertStationIds={alertStationIds}
          selectedRank={selectedRank}
          onSelectHotspot={onSelectHotspot}
          loading={loading}
        />

        <div className="map-col">
          {meta ? (
            <MapView
              center={center}
              cases={cases}
              hotspots={hotspots}
              districtStats={districtStats}
              activeDistrictId={filters.districtId}
              onDrillDistrict={(id) => onFilters({ ...filters, districtId: id })}
              alertStationIds={alertStationIds}
              selectedRank={selectedRank}
              onSelectHotspot={onSelectHotspot}
            />
          ) : (
            <div className="map-loading">
              {error ? `Backend unreachable — ${error}` : "Connecting to analytics API…"}
            </div>
          )}
          {selected && (
            <HotspotDetail
              hotspot={selected}
              cases={cases}
              hasActiveAlert={selected.station_id != null && alertStationIds.has(selected.station_id)}
              onClose={() => setSelectedRank(null)}
            />
          )}
        </div>
      </div>
      )}
    </div>
  );
}
