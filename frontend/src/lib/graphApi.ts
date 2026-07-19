/**
 * Typed client for the graph exploration API (GRAPH-003/#45).
 * Every edge carries provenance (evidence_case_id, derivation,
 * classification); every response carries the #25 intelligence envelope.
 */
import { API_BASE } from "./api";

export type NodeType =
  | "CASE"
  | "ACCUSED_RECORD"
  | "VICTIM_RECORD"
  | "POLICE_STATION"
  | "DISTRICT"
  | "CRIME_HEAD"
  | "CRIME_SUBHEAD"
  | "COURT"
  | "SECTION";

export type Classification =
  | "FACT"
  | "DERIVED_METRIC"
  | "STATISTICAL_INFERENCE"
  | "AI_DERIVED"
  | "POTENTIAL_ASSOCIATION"
  | "HUMAN_CONFIRMED";

export interface GraphNode {
  node_id: string;
  node_type: NodeType;
  entity_ref_id: string;
  label: string;
  depth: number;
}

export interface GraphEdge {
  edge_id: string;
  source: string;
  target: string;
  relationship_type: string;
  weight: number;
  evidence_case_id: number;
  derivation: string;
  classification: Classification;
}

export interface SubgraphStubs {
  truncated: { node_id: string; more_edges: number }[];
  cross_scope: { node_id: string; cross_scope_edges: number }[];
}

export interface Subgraph {
  seed: string;
  depth: number;
  node_count: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  stubs: SubgraphStubs;
  intelligence: IntelligenceEnvelope;
}

export interface NodeMetrics {
  component_id: string;
  community_id: string;
  degree: number;
  degree_centrality: number;
  betweenness: number;
  co_occurrence_count: number;
  is_case_size_artifact: boolean;
  interpretation: string | null;
  classification: Classification;
  method_version: string;
  run_id: string;
}

export interface NodeDetail {
  node: Omit<GraphNode, "depth">;
  metrics: NodeMetrics | null;
  linked_cases: number[];
  edge_type_counts: Record<string, number>;
  edges: GraphEdge[];
  intelligence: IntelligenceEnvelope;
}

export interface IntelligenceEnvelope {
  classification: Classification;
  classification_label: string;
  method: { method_name: string; method_version: string; model_version?: string };
  limitations?: string[];
}

export interface ClassificationInfo {
  classification: Classification;
  label: string;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function fetchSubgraph(
  seedType: NodeType,
  seedId: string,
  opts: { depth?: number; limit?: number } = {},
): Promise<Subgraph> {
  const p = new URLSearchParams({ seed_type: seedType, seed_id: seedId });
  if (opts.depth) p.set("depth", String(opts.depth));
  if (opts.limit) p.set("limit", String(opts.limit));
  return get(`/api/v1/graph/subgraph?${p}`);
}

export function fetchNodeDetail(nodeType: NodeType, refId: string): Promise<NodeDetail> {
  return get(`/api/v1/graph/nodes/${nodeType}/${encodeURIComponent(refId)}`);
}

/** Attribute filters for association search (all optional, AND-combined). */
export interface AssocFilters {
  subhead_id?: string;
  district_id?: string;
  station_id?: string;
  name_contains?: string;
  name_exact?: string;
  age_min?: number;
  age_max?: number;
  gender?: string;
  date_from?: string;
  date_to?: string;
}

export interface AssociationResult {
  seed: { case_id: string; subhead: string; station: string; district: string } | null;
  focus: string | null;
  channel: string | null;
  association_count: number;
  total_related: number;
  /** node_id -> number of related cases reachable by expanding it (overview hint). */
  expandable: Record<string, number>;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** Investigative association search for a seed case (same-suspect + shared
 *  entities), with server-side attribute filters (orthogonal to the View).
 *
 *  focus omitted  -> the overview: the seed case + its own entities, each
 *                    carrying an `expandable` count.
 *  focus="TYPE:id" -> expand that one entity into its related cases (to merge
 *                    into the current graph). */
export function fetchAssociations(
  caseId: string,
  filters: AssocFilters = {},
  focus?: string,
): Promise<AssociationResult> {
  const p = new URLSearchParams({ case_id: caseId });
  if (focus) p.set("focus", focus);
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  }
  return get(`/api/associations?${p}`);
}

export function fetchClassifications(): Promise<ClassificationInfo[]> {
  return get(`/api/classifications`);
}

/** Cheap default seed for first paint: the earliest case id. */
export async function fetchSeedCaseId(): Promise<string | null> {
  const r = await get<{ cases: { CaseMasterID: string }[] }>(
    `/api/cases?limit=1&with_coords=false`,
  );
  return r.cases[0]?.CaseMasterID ?? null;
}
