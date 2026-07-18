/**
 * Interactive crime map (Phase 3). MapLibre GL over a free CARTO dark basemap
 * (no API token). Plots geolocated cases as points and detected hotspots as
 * true-radius rings, with click-to-inspect on each hotspot.
 */
import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { CaseRecord, DistrictStat, Hotspot } from "../lib/api";
import { circlePolygon, featureCollection, pointFeature } from "../lib/geo";

const CASE_SRC = "cases";
const HOT_FILL_SRC = "hotspot-fills";
const HOT_PT_SRC = "hotspot-centers";
const DIST_SRC = "districts";

/** Velocity → sequential-blue fill (cool = steady/cooling, bright = rising). */
function velocityColor(v: number | null): string {
  if (v == null || v < 0.95) return "#24425f";
  if (v < 1.1) return "#256abf";
  if (v < 1.25) return "#3987e5";
  return "#6da7ec";
}

// Free, token-less dark basemap (CARTO). Attribution required.
const STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    carto: {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
      ],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors © CARTO",
    },
  },
  layers: [{ id: "carto", type: "raster", source: "carto" }],
};

interface Props {
  center: { lat: number; lon: number };
  cases: CaseRecord[];
  hotspots: Hotspot[];
  districtStats: DistrictStat[];
  activeDistrictId: string | null;
  onDrillDistrict: (districtId: string) => void;
  alertStationIds: Set<string>;
  selectedRank: number | null;
  onSelectHotspot: (h: Hotspot | null) => void;
}

export function MapView({
  center,
  cases,
  hotspots,
  districtStats,
  activeDistrictId,
  onDrillDistrict,
  alertStationIds,
  selectedRank,
  onSelectHotspot,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const readyRef = useRef(false);
  const pulseMarkersRef = useRef<maplibregl.Marker[]>([]);
  const districtGeoRef = useRef<GeoJSON.FeatureCollection | null>(null);
  const onSelectRef = useRef(onSelectHotspot);
  onSelectRef.current = onSelectHotspot;
  const onDrillRef = useRef(onDrillDistrict);
  onDrillRef.current = onDrillDistrict;

  // --- create the map once ---
  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE,
      center: [center.lon, center.lat],
      zoom: 9,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    mapRef.current = map;

    map.on("load", () => {
      map.addSource(CASE_SRC, { type: "geojson", data: featureCollection([]) });
      map.addSource(HOT_FILL_SRC, { type: "geojson", data: featureCollection([]) });
      map.addSource(HOT_PT_SRC, { type: "geojson", data: featureCollection([]) });
      map.addSource(DIST_SRC, { type: "geojson", data: featureCollection([]) });

      // district choropleth (case velocity) — beneath everything else
      map.addLayer({
        id: "district-fill",
        type: "fill",
        source: DIST_SRC,
        paint: { "fill-color": ["get", "fill"], "fill-opacity": 0.4 },
      });
      map.addLayer({
        id: "district-border",
        type: "line",
        source: DIST_SRC,
        paint: { "line-color": "#5b6b7a", "line-width": 1 },
      });

      // case points
      map.addLayer({
        id: "case-points",
        type: "circle",
        source: CASE_SRC,
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 2.2, 14, 5],
          "circle-color": "#3987e5",
          "circle-opacity": 0.55,
          "circle-stroke-width": 0.5,
          "circle-stroke-color": "#0d0d0d",
        },
      });

      // hotspot fill + outline (true radius). Selected ring is emphasised.
      map.addLayer({
        id: "hotspot-fill",
        type: "fill",
        source: HOT_FILL_SRC,
        paint: {
          "fill-color": "#d03b3b",
          "fill-opacity": ["case", ["==", ["get", "rank"], ["literal", -1]], 0.28, 0.14],
        },
      });
      map.addLayer({
        id: "hotspot-outline",
        type: "line",
        source: HOT_FILL_SRC,
        paint: {
          "line-color": "#d03b3b",
          "line-width": ["case", ["get", "selected"], 3, 1.5],
          "line-opacity": 0.9,
        },
      });

      // hotspot center label (case count)
      map.addLayer({
        id: "hotspot-count",
        type: "symbol",
        source: HOT_PT_SRC,
        layout: {
          "text-field": ["to-string", ["get", "case_count"]],
          "text-size": 13,
          "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
          "text-allow-overlap": true,
        },
        paint: {
          "text-color": "#ffffff",
          "text-halo-color": "#d03b3b",
          "text-halo-width": 1.6,
        },
      });

      readyRef.current = true;
      syncData();

      // load the (static, external) district boundaries, then paint the choropleth
      fetch("karnataka-districts.geojson")
        .then((r) => r.json())
        .then((geo: GeoJSON.FeatureCollection) => {
          districtGeoRef.current = geo;
          updateDistricts();
          fitToData();
        })
        .catch(() => fitToData());

      // district drill + hover
      const dpopup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 });
      map.on("click", "district-fill", (e) => {
        const id = e.features?.[0]?.properties?.district_id;
        if (id) onDrillRef.current(String(id));
      });
      map.on("mousemove", "district-fill", (e) => {
        const p = e.features?.[0]?.properties as Record<string, string> | undefined;
        if (!p) return;
        map.getCanvas().style.cursor = "pointer";
        dpopup
          .setLngLat(e.lngLat)
          .setHTML(
            `<div class="popup-title">${p.district_name}</div>` +
              `<div class="popup-row">${p.case_count} cases · velocity ${p.velocity ?? "—"}</div>` +
              `<div class="popup-row">click to drill in</div>`,
          )
          .addTo(map);
      });
      map.on("mouseleave", "district-fill", () => {
        map.getCanvas().style.cursor = "";
        dpopup.remove();
      });

      // interactions
      const clickable = ["hotspot-fill", "hotspot-count"];
      for (const layer of clickable) {
        map.on("click", layer, (e) => {
          const f = e.features?.[0];
          if (!f) return;
          const rank = Number(f.properties?.rank);
          onSelectRef.current(hotspotsRef.current.find((h) => h.rank === rank) ?? null);
        });
        map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
      }

      // case hover popup
      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 });
      map.on("mouseenter", "case-points", (e) => {
        map.getCanvas().style.cursor = "pointer";
        const f = e.features?.[0];
        if (!f) return;
        const p = f.properties as Record<string, string>;
        popup
          .setLngLat((f.geometry as GeoJSON.Point).coordinates as [number, number])
          .setHTML(
            `<div class="popup-title">${p.subhead_name}</div>` +
              `<div class="popup-row">${p.station_name}</div>` +
              `<div class="popup-row">${p.incident_from ?? p.registered_date ?? ""}</div>`,
          )
          .addTo(map);
      });
      map.on("mouseleave", "case-points", () => {
        map.getCanvas().style.cursor = "";
        popup.remove();
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
      readyRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // keep latest hotspots reachable inside map event handlers
  const hotspotsRef = useRef<Hotspot[]>(hotspots);
  hotspotsRef.current = hotspots;

  function syncData() {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;

    const casePts = cases
      .filter((c) => c.latitude != null && c.longitude != null)
      .map((c) =>
        pointFeature(c.latitude!, c.longitude!, {
          subhead_name: c.subhead_name,
          station_name: c.station_name,
          incident_from: c.incident_from ?? "",
          registered_date: c.registered_date ?? "",
        }),
      );
    (map.getSource(CASE_SRC) as maplibregl.GeoJSONSource)?.setData(featureCollection(casePts));

    const fills = hotspots.map((h) =>
      circlePolygon(h.center.lat, h.center.lon, h.radius_m, {
        rank: h.rank,
        case_count: h.case_count,
        selected: h.rank === selectedRank,
      }),
    );
    (map.getSource(HOT_FILL_SRC) as maplibregl.GeoJSONSource)?.setData(featureCollection(fills));

    const centers = hotspots.map((h) =>
      pointFeature(h.center.lat, h.center.lon, { rank: h.rank, case_count: h.case_count }),
    );
    (map.getSource(HOT_PT_SRC) as maplibregl.GeoJSONSource)?.setData(featureCollection(centers));
  }

  // Pulsing markers bind to ACTIVE trend alerts only — a hotspot pulses iff its
  // station has an active alert. No alert -> no pulse (a pulse without an alert
  // is prohibited, #61). Rendered as pointer-through HTML markers so clicks
  // still reach the hotspot layer beneath.
  function updatePulseMarkers() {
    const map = mapRef.current;
    if (!map) return;
    for (const m of pulseMarkersRef.current) m.remove();
    pulseMarkersRef.current = [];
    for (const h of hotspots) {
      if (!h.station_id || !alertStationIds.has(h.station_id)) continue;
      const el = document.createElement("div");
      el.className = "pulse-marker";
      el.style.pointerEvents = "none";
      pulseMarkersRef.current.push(
        new maplibregl.Marker({ element: el }).setLngLat([h.center.lon, h.center.lat]).addTo(map),
      );
    }
  }

  // Paint the district choropleth by case velocity; the fill is baked into each
  // feature's `fill` property. Fills show at the state level and hide once a
  // district is drilled into (borders stay for context).
  function updateDistricts() {
    const map = mapRef.current;
    const geo = districtGeoRef.current;
    if (!map || !readyRef.current || !geo) return;
    const byId = new Map(districtStats.map((d) => [d.district_id, d]));
    const feats = geo.features.map((f) => {
      const id = String(f.properties?.district_id);
      const st = byId.get(id);
      return {
        ...f,
        properties: {
          ...f.properties,
          fill: velocityColor(st?.velocity ?? null),
          case_count: st?.case_count ?? 0,
          velocity: st?.velocity ?? null,
        },
      };
    });
    (map.getSource(DIST_SRC) as maplibregl.GeoJSONSource)?.setData({
      type: "FeatureCollection",
      features: feats,
    });
    if (map.getLayer("district-fill")) {
      map.setLayoutProperty("district-fill", "visibility", activeDistrictId ? "none" : "visible");
    }
  }

  function fitToData() {
    const map = mapRef.current;
    if (!map) return;
    const pts = cases.filter((c) => c.latitude != null && c.longitude != null);
    if (pts.length === 0) return;
    const b = new maplibregl.LngLatBounds();
    for (const c of pts) b.extend([c.longitude!, c.latitude!]);
    map.fitBounds(b, { padding: 60, maxZoom: 13, duration: 600 });
  }

  // re-sync sources whenever data or selection changes
  useEffect(() => {
    syncData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cases, hotspots, selectedRank]);

  // (re)bind the alert pulse whenever hotspots or active alerts change
  useEffect(() => {
    updatePulseMarkers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hotspots, alertStationIds]);

  // repaint the district choropleth on stats or drill-scope change
  useEffect(() => {
    updateDistricts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [districtStats, activeDistrictId]);

  // refit the viewport when the underlying case set changes (filter change)
  useEffect(() => {
    fitToData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cases]);

  // fly to a hotspot when it is selected from the list
  useEffect(() => {
    const map = mapRef.current;
    if (!map || selectedRank == null) return;
    const h = hotspots.find((x) => x.rank === selectedRank);
    if (h) map.flyTo({ center: [h.center.lon, h.center.lat], zoom: 14, duration: 700 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRank]);

  return (
    <div className="map-wrap">
      <div className="map" ref={containerRef} />
      <div className="legend">
        <strong>Map layers</strong>
        <div className="row">
          <span className="swatch sq" style={{ background: "#3987e5", opacity: 0.5 }} />
          District (shade = case velocity)
        </div>
        <div className="row">
          <span className="swatch" style={{ background: "#3987e5", opacity: 0.7 }} />
          Individual case (FIR)
        </div>
        <div className="row">
          <span className="ring" />
          Detected hotspot (true radius)
        </div>
        <div className="row">
          <span className="ring pulsing" />
          Active trend alert (pulsing)
        </div>
      </div>
    </div>
  );
}
