/**
 * KAVACH AI — interactive crime hotspot console (Phase 3).
 * Loads dataset meta, then drives the /cases and /hotspots endpoints from a
 * shared filter (crime type + recency). All data is SYNTHETIC (ADR-011) — the
 * persistent banner makes that explicit.
 */
import { useCallback, useEffect, useState } from "react";
import {
  fetchCases,
  fetchHotspots,
  fetchMeta,
  type CaseRecord,
  type Filters,
  type Hotspot,
  type Meta,
} from "../lib/api";
import { MapView } from "./MapView";
import { Sidebar } from "./Sidebar";
import { HotspotDetail } from "./HotspotDetail";
import { Overview } from "./Overview";
import "./styles.css";

const DEFAULT_FILTERS: Filters = { subheadId: null, days: null };

type View = "overview" | "map";

export function App() {
  const [view, setView] = useState<View>("overview");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [selectedRank, setSelectedRank] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // load dataset meta once (also gives the latest date for recency windows)
  useEffect(() => {
    fetchMeta().then(setMeta).catch((e) => setError(String(e)));
  }, []);

  // (re)query cases + hotspots whenever filters change
  useEffect(() => {
    if (!meta) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const latest = meta.date_range.to;
    Promise.all([fetchCases(filters, latest), fetchHotspots(filters)])
      .then(([c, h]) => {
        if (cancelled) return;
        setCases(c.cases);
        setHotspots(h.hotspots);
        setSelectedRank(null);
      })
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [meta, filters]);

  const onSelectHotspot = useCallback((h: Hotspot | null) => {
    setSelectedRank(h ? h.rank : null);
  }, []);

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
          onFilters={setFilters}
          caseCount={cases.length}
          hotspots={hotspots}
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
              selectedRank={selectedRank}
              onSelectHotspot={onSelectHotspot}
            />
          ) : (
            <div className="map-loading">
              {error ? `Backend unreachable — ${error}` : "Connecting to analytics API…"}
            </div>
          )}
          {selected && (
            <HotspotDetail hotspot={selected} onClose={() => setSelectedRank(null)} />
          )}
        </div>
      </div>
      )}
    </div>
  );
}
