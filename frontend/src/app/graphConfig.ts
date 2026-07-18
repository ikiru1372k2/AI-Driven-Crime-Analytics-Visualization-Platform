/** Static config for the association graph view (colours, seed presets, lenses).
 *  Kept out of GraphView.tsx so the component stays under the source-size gate. */
import type { NodeType } from "../lib/graphApi";

/** Node colours by type (status-neutral palette; classification colours
 *  are reserved for edges so inference-vs-fact stays unambiguous). */
export const NODE_COLORS: Record<string, string> = {
  CASE: "#4f7cc9",
  ACCUSED_RECORD: "#a76fb9",
  VICTIM_RECORD: "#5aa9a3",
  POLICE_STATION: "#7d8a97",
  DISTRICT: "#5b6d84",
  CRIME_HEAD: "#c98a4f",
  CRIME_SUBHEAD: "#c9a94f",
  COURT: "#8a7dc9",
  SECTION: "#6f8f5a",
};

/** Edge styling by classification — the provenance-first rule (#25/#43):
 *  observed FACT restatements: solid grey; DERIVED_METRIC co-occurrence:
 *  solid blue; POTENTIAL_ASSOCIATION (identity candidates / MO similarity):
 *  dashed amber; HUMAN_CONFIRMED identity: solid green, heavy. */
export const EDGE_STYLE: Record<string, { color: string; style: string; width: number }> = {
  FACT: { color: "#9aa4ae", style: "solid", width: 1.5 },
  DERIVED_METRIC: { color: "#4f7cc9", style: "solid", width: 2.5 },
  STATISTICAL_INFERENCE: { color: "#4f7cc9", style: "solid", width: 2.5 },
  AI_DERIVED: { color: "#d9a13b", style: "dashed", width: 2.5 },
  POTENTIAL_ASSOCIATION: { color: "#d9a13b", style: "dashed", width: 2.5 },
  HUMAN_CONFIRMED: { color: "#3c9a5f", style: "solid", width: 4 },
};

export const SEED_TYPES: NodeType[] = ["CASE", "ACCUSED_RECORD", "POLICE_STATION", "DISTRICT"];

/** A resolvable example id per seed type — used for the placeholder and to
 *  auto-fill a valid id when the type changes, so you can't seed a CASE id
 *  against an ACCUSED_RECORD (which 404s as "unknown node"). */
export const SEED_EXAMPLES: Record<string, string> = {
  CASE: "7231",
  ACCUSED_RECORD: "2238", // "Ravi Kumar" — the identity fragment on the Identities tab
  POLICE_STATION: "4430", // Peenya PS (the hotspot)
  DISTRICT: "44", // Bengaluru City
};

/** Default sample seed — case 7231, whose accused is the "Ravi Kumar" identity
 *  fragment surfaced on the Identities tab (coherent cross-feature demo). */
export const DEFAULT_SEED_CASE = SEED_EXAMPLES.CASE;

/** Lenses — like a map's view switcher, each shows one relationship dimension
 *  so the graph isn't all node types at once. CASE is the connective spine and
 *  the seed node is always kept. `types: null` = show everything. */
export type LensKey = "full" | "people" | "places" | "charge";
export const LENSES: { key: LensKey; label: string; types: Set<string> | null }[] = [
  { key: "full", label: "Full", types: null },
  { key: "people", label: "People", types: new Set(["CASE", "ACCUSED_RECORD", "VICTIM_RECORD"]) },
  { key: "places", label: "Places", types: new Set(["CASE", "POLICE_STATION", "DISTRICT"]) },
  {
    key: "charge",
    label: "Charge",
    types: new Set(["CASE", "CRIME_HEAD", "CRIME_SUBHEAD", "SECTION", "COURT"]),
  },
];
