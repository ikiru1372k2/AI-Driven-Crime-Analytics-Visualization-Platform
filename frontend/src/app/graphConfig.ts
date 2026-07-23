/** Static config for the association graph view (colours, seed presets, lenses).
 *  Kept out of GraphView.tsx so the component stays under the source-size gate. */
import type cytoscape from "cytoscape";
import type { AssocFilters, GraphEdge, GraphNode, NodeType } from "../lib/graphApi";

/** Node colours by type (status-neutral palette; classification colours
 *  are reserved for edges so inference-vs-fact stays unambiguous). Grouped by
 *  family: people (purple/teal), places (blues/greys), charges (warm + green). */
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

/** Human labels for the node-type legend, in a sensible reading order
 *  (the connective spine first, then people, places, charges). */
export const NODE_LEGEND: { type: string; label: string }[] = [
  { type: "CASE", label: "Case (FIR)" },
  { type: "ACCUSED_RECORD", label: "Accused" },
  { type: "VICTIM_RECORD", label: "Victim" },
  { type: "POLICE_STATION", label: "Police station" },
  { type: "DISTRICT", label: "District" },
  { type: "CRIME_SUBHEAD", label: "Crime type" },
  { type: "CRIME_HEAD", label: "Crime head" },
  { type: "SECTION", label: "IPC section" },
  { type: "COURT", label: "Court" },
];

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

/** A saved view for the Back stack: the graph AND everything the stats bar /
 *  pager / zoom read from, so Back restores a view exactly as it was. */
export interface ViewSnapshot {
  nodes: Map<string, GraphNode>;
  edges: Map<string, GraphEdge>;
  type: NodeType;
  id: string;
  pageInfo: { total: number; offset: number; count: number } | null;
  activeFocus: string | null;
  focusId: string | null;
  expandable: Record<string, number>;
  page: number;
  drilled: boolean;
  filters: AssocFilters;
  resultCount: number | null;
}

/** A specific loading line for an expansion, so the cover tells the user exactly
 *  what's being fetched (e.g. "Loading theft cases similar to this case…"). */
export function expandLoadingMessage(type: NodeType, label: string): string {
  const what = label?.trim() || "these";
  switch (type) {
    case "CRIME_SUBHEAD":
    case "CRIME_HEAD":
    case "SECTION":
      return `Loading ${what} cases similar to this case…`;
    case "DISTRICT":
    case "POLICE_STATION":
    case "COURT":
      return `Loading cases in ${what} similar to this case…`;
    case "ACCUSED_RECORD":
    case "VICTIM_RECORD":
      return `Finding other records for ${what}…`;
    default:
      return "Loading similar cases…";
  }
}

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
/** View dimensions — multi-select projection (which node types to draw). CASE
 *  is the connective spine and is always shown; the seed node is always kept. */
export const VIEW_DIMS: { key: string; label: string; types: string[] }[] = [
  { key: "people", label: "People", types: ["ACCUSED_RECORD", "VICTIM_RECORD"] },
  { key: "places", label: "Places", types: ["POLICE_STATION", "DISTRICT"] },
  { key: "charges", label: "Charges", types: ["CRIME_HEAD", "CRIME_SUBHEAD", "SECTION", "COURT"] },
];
export const ALL_VIEW_KEYS = VIEW_DIMS.map((d) => d.key);

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

/** Build cytoscape elements from the merged graph, applying the View projection
 *  (CASE + checked dimensions; seed always kept), dropping edges whose endpoints
 *  aren't both visible and disconnected non-seed nodes, and sizing nodes by
 *  degree. Nodes carry no related-case counts (PERF-001): expandability is a
 *  hover/tap affordance, not a badged number.
 *  Pure + extracted so GraphView stays under the source-size gate. */
export function buildGraphElements(
  merged: { nodes: Map<string, GraphNode>; edges: Map<string, GraphEdge> },
  viewDims: Set<string>,
  seedNodeId: string,
) {
  const allowed = new Set<string>(["CASE"]);
  for (const d of VIEW_DIMS) if (viewDims.has(d.key)) d.types.forEach((t) => allowed.add(t));
  const nodes = [...merged.nodes.values()].filter(
    (n) => allowed.has(n.node_type) || n.node_id === seedNodeId,
  );
  const visibleIds = new Set(nodes.map((n) => n.node_id));
  const edges = [...merged.edges.values()].filter(
    (e) => visibleIds.has(e.source) && visibleIds.has(e.target),
  );
  const degree = new Map<string, number>();
  for (const e of edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
  }
  const maxDeg = Math.max(1, ...degree.values());
  const shownNodes = nodes.filter(
    (n) => (degree.get(n.node_id) ?? 0) > 0 || n.node_id === seedNodeId,
  );
  return [
    ...shownNodes.map((n) => ({
      data: {
        id: n.node_id,
        label: n.label,
        type: n.node_type,
        ref: n.entity_ref_id,
        deg: degree.get(n.node_id) ?? 0,
        degNorm: (degree.get(n.node_id) ?? 0) / maxDeg,
      },
    })),
    ...edges.map((e) => ({
      data: {
        id: e.edge_id,
        source: e.source,
        target: e.target,
        classification: e.classification,
        rel: e.relationship_type,
        weight: e.weight,
      },
    })),
  ];
}

/** Whether a node offers "Navigate here". Places/charges/cases always do.
 *  People (accused/victim) do ONLY when they have an identity match under a
 *  DIFFERENT name (an `expandable` same-suspect count) that is NOT already
 *  drawn — navigating should reveal something new. Once those associations are
 *  on screen (a SAME_IDENTITY edge touches the node), there's nothing to add. */
export function canNavigateNode(
  node: { node_type: string; entity_ref_id: string; node_id?: string } | undefined,
  expandable: Record<string, number>,
  edges: Map<string, GraphEdge>,
): boolean {
  if (!node) return false;
  if (node.node_type !== "ACCUSED_RECORD" && node.node_type !== "VICTIM_RECORD") return true;
  const nid = node.node_id ?? `${node.node_type}:${node.entity_ref_id}`;
  for (const e of edges.values()) {
    if (e.relationship_type === "SAME_IDENTITY" && (e.source === nid || e.target === nid)) {
      return false; // its different-name associations are already shown
    }
  }
  return (expandable[nid] ?? 0) > 0; // has variants still to reveal
}

/** Cytoscape stylesheet for the graph, themed. Extracted here to keep
 *  GraphView under the source-size gate. */
export function buildCyStyle(theme: "dark" | "light") {
  const labelInk = theme === "light" ? "#0b0b0b" : "#e8eef4";
  const labelHalo = theme === "light" ? "#ffffff" : "#12161b";
  return [
    {
      selector: "node",
      style: {
        label: "data(label)",
        // size by degree: hubs large, leaf records small
        width: "mapData(degNorm, 0, 1, 16, 52)",
        height: "mapData(degNorm, 0, 1, 16, 52)",
        "background-color": (el: cytoscape.NodeSingular) =>
          NODE_COLORS[el.data("type") as string] ?? "#888",
        "border-width": 1.5,
        "border-color": theme === "light" ? "#ffffff" : "#12161b",
        // label styling: bigger for hubs; a halo keeps text legible on the graph
        "font-size": "mapData(degNorm, 0, 1, 8, 15)",
        color: labelInk,
        "text-outline-color": labelHalo,
        "text-outline-width": 2,
        "text-wrap": "ellipsis",
        "text-max-width": "120px",
        "text-valign": "bottom",
        "text-margin-y": 3,
        // hide labels when zoomed out; small (leaf) labels drop out first
        "min-zoomed-font-size": 11,
      },
    },
    {
      selector: "node:selected",
      style: {
        "border-width": 3,
        "border-color": theme === "light" ? "#0b0b0b" : "#e8eef4",
        "min-zoomed-font-size": 0,
        "font-size": 13,
        "z-index": 10,
      },
    },
    { selector: "node.hover", style: { "min-zoomed-font-size": 0, "z-index": 9 } },
    {
      selector: "edge",
      style: {
        "curve-style": "bezier",
        "line-color": (el: cytoscape.EdgeSingular) =>
          (EDGE_STYLE[el.data("classification") as string] ?? EDGE_STYLE.FACT).color,
        "line-style": (el: cytoscape.EdgeSingular) =>
          (EDGE_STYLE[el.data("classification") as string] ?? EDGE_STYLE.FACT)
            .style as cytoscape.Css.LineStyle,
        width: (el: cytoscape.EdgeSingular) =>
          (EDGE_STYLE[el.data("classification") as string] ?? EDGE_STYLE.FACT).width,
        opacity: 0.55,
      },
    },
    { selector: "edge:selected", style: { opacity: 1, width: 5 } },
    { selector: "node:selected, node.hover", style: {} },
    { selector: "edge.incident", style: { opacity: 0.9 } },
    { selector: ".dim", style: { opacity: 0.08 } },
  ];
}
