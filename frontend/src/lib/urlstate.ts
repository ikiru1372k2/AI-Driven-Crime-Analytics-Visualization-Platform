/**
 * URL-addressable console state (#61). Serialises the view, filters and the
 * selected hotspot into the location hash so any drill-down is shareable and
 * survives a reload — e.g. `#view=map&subhead=71&district=44&days=90&hotspot=1`.
 */
import type { Filters } from "./api";

export interface HashState {
  view:
    | "overview"
    | "map"
    | "graph"
    | "identities"
    | "evidence"
    | "mo"
    | "anomalies"
    | "forecast";
  filters: Partial<Filters>;
  hotspot: number | null;
  /** graph seed as "TYPE:id", e.g. "ACCUSED_RECORD:2238" (#63) */
  graphSeed: string | null;
}

export function readHashState(): HashState {
  const p = new URLSearchParams(location.hash.replace(/^#/, ""));
  const filters: Partial<Filters> = {};
  if (p.get("subhead")) filters.subheadId = p.get("subhead");
  if (p.get("district")) filters.districtId = p.get("district");
  if (p.get("days")) filters.days = Number(p.get("days"));
  const h = p.get("hotspot");
  const v = p.get("view");
  const view =
    v === "map"
      ? "map"
      : v === "graph"
        ? "graph"
        : v === "identities"
          ? "identities"
          : v === "evidence"
            ? "evidence"
            : v === "mo"
              ? "mo"
              : v === "anomalies"
                ? "anomalies"
                : v === "forecast"
                  ? "forecast"
                  : "overview";
  return {
    view,
    filters,
    hotspot: h ? Number(h) : null,
    graphSeed: p.get("seed"),
  };
}

export function writeHashState(s: {
  view: string;
  filters: Filters;
  hotspot: number | null;
  graphSeed?: string | null;
}): void {
  const p = new URLSearchParams();
  p.set("view", s.view);
  if (s.filters.subheadId) p.set("subhead", s.filters.subheadId);
  if (s.filters.districtId) p.set("district", s.filters.districtId);
  if (s.filters.days != null) p.set("days", String(s.filters.days));
  if (s.hotspot != null) p.set("hotspot", String(s.hotspot));
  if (s.graphSeed) p.set("seed", s.graphSeed);
  const next = "#" + p.toString();
  if (location.hash !== next) history.replaceState(null, "", next);
}
