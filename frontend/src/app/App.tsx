/**
 * KAVACH AI — interactive crime hotspot console (Phase 3).
 * Loads dataset meta, then drives the /cases and /hotspots endpoints from a
 * shared filter (crime type + recency). All data is SYNTHETIC (ADR-011) — the
 * persistent banner makes that explicit.
 */
import { useCallback, useEffect, useState } from "react";
import {
  fetchAnomalies,
  fetchCases,
  fetchDistricts,
  fetchHotspots,
  fetchMeta,
  fetchOverview,
  fetchRankedAccused,
  fetchRisk,
  fetchTrends,
  type CaseRecord,
  type DistrictStat,
  type Filters,
  type Hotspot,
  type Meta,
  type TrendAlert,
} from "../lib/api";
import { prefetchQuery } from "../lib/queryCache";
import { MapView } from "./MapView";
import { Sidebar } from "./Sidebar";
import { HotspotDetail } from "./HotspotDetail";
import { Overview } from "./Overview";
import { IdentityExplorer, type IdentitySearchSeed } from "./IdentityExplorer";
import { GraphView, type GraphSeed } from "./GraphView";
import { MoView } from "./MoView";
import { ForecastView } from "./ForecastView";
import { AnomaliesView } from "./AnomaliesView";
import { CommandNav, type ModuleView } from "./CommandNav";
import { TimeScrubber } from "./TimeScrubber";
import type { NodeType, PersonDetail } from "../lib/graphApi";
import { readHashState, writeHashState } from "../lib/urlstate";
import { initialTheme, applyTheme, type Theme } from "../lib/theme";
import "./styles.css";

const DEFAULT_FILTERS: Filters = { subheadId: null, districtId: null, days: null };

type View = ModuleView;

function parseSeed(raw: string | null): GraphSeed | null {
  if (!raw) return null;
  const [type, ...rest] = raw.split(":");
  return rest.length ? { type: type as NodeType, id: rest.join(":") } : null;
}

export function App() {
  const initial = readHashState();
  const [view, setView] = useState<View>(initial.view);
  const [theme, setTheme] = useState<Theme>(initialTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [filters, setFilters] = useState<Filters>({ ...DEFAULT_FILTERS, ...initial.filters });
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [alerts, setAlerts] = useState<TrendAlert[]>([]);
  const [districtStats, setDistrictStats] = useState<DistrictStat[]>([]);
  const [flagCount, setFlagCount] = useState(0);
  const [selectedRank, setSelectedRank] = useState<number | null>(initial.hotspot);
  const [graphSeed, setGraphSeed] = useState<GraphSeed | null>(parseSeed(initial.graphSeed));
  const [identitySeed, setIdentitySeed] = useState<IdentitySearchSeed | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // load dataset meta + district velocity once (static for a demo run)
  useEffect(() => {
    fetchMeta().then(setMeta).catch((e) => setError(String(e)));
    fetchDistricts().then((d) => setDistrictStats(d.districts)).catch(() => {});
    fetchAnomalies().then((a) => setFlagCount(a.flag_count)).catch(() => {});
  }, []);

  // Warm the heavy tabs in the background at startup (PERF-001) so switching to
  // Overview/Anomalies/Area-Risk/Identities paints from cache instead of showing
  // a spinner. Same keys+fetchers as each tab's useCachedQuery, so the warm
  // entry is reused; fire-and-forget, deduped, and skipped if already fresh.
  useEffect(() => {
    prefetchQuery("overview", fetchOverview);
    prefetchQuery("anomalies:30", () => fetchAnomalies(30));
    prefetchQuery("risk:30", () => fetchRisk(30));
    prefetchQuery("accused:ranked:0", () => fetchRankedAccused(15, 0)); // page 1, PAGE=15
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
    writeHashState({
      view,
      filters,
      hotspot: selectedRank,
      graphSeed: graphSeed ? `${graphSeed.type}:${graphSeed.id}` : null,
    });
  }, [view, filters, selectedRank, graphSeed]);

  // changing a filter invalidates the current hotspot selection
  const onFilters = useCallback((f: Filters) => {
    setFilters(f);
    setSelectedRank(null);
  }, []);

  const onSelectHotspot = useCallback((h: Hotspot | null) => {
    setSelectedRank(h ? h.rank : null);
  }, []);

  // "See similar people" in the graph → open Identities and run that person's search.
  const seeSimilarPerson = useCallback((p: PersonDetail) => {
    setIdentitySeed({ name: p.name ?? "", age: p.age, sex: p.gender });
    setView("identities");
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

      <CommandNav
        view={view}
        onView={setView}
        alertCount={alerts.length}
        identityCount={0}
        flagCount={flagCount}
        theme={theme}
        onToggleTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
      />

      {view === "overview" && <Overview onOpenMap={() => setView("map")} />}

      {view === "identities" && (
        <IdentityExplorer
          initialSearch={identitySeed}
          onSearchConsumed={() => setIdentitySeed(null)}
        />
      )}

      {view === "mo" && <MoView />}

      {view === "forecast" && (
        <ForecastView
          onOpenCase={(caseId) => {
            setGraphSeed({ type: "CASE", id: String(caseId) });
            setView("graph");
          }}
        />
      )}

      {view === "anomalies" && (
        <AnomaliesView
          onOpenCase={(caseId) => {
            setGraphSeed({ type: "CASE", id: String(caseId) });
            setView("graph");
          }}
        />
      )}

      {view === "graph" && (
        <GraphView
          seed={graphSeed}
          onSeed={setGraphSeed}
          theme={theme}
          onSeeSimilar={seeSimilarPerson}
        />
      )}

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
              theme={theme}
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
          {meta && <TimeScrubber filters={filters} onFilters={onFilters} />}
        </div>
      </div>
      )}
    </div>
  );
}
