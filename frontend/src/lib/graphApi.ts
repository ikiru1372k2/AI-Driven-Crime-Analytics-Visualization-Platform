/**
 * Typed client for the graph exploration API (GRAPH-003/#45).
 * Every edge carries provenance (evidence_case_id, derivation,
 * classification); every response carries the #25 intelligence envelope.
 */
import { API_BASE, DEV_AUTH_HEADERS } from "./api";

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
  const res = await fetch(`${API_BASE}${path}`, { headers: DEV_AUTH_HEADERS });
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

/** A person named on a case (accused or victim) — a plain fact restatement. */
export interface CasePerson {
  name: string | null;
  age: number | null;
  gender: string | null;
}

/** Everything we know about one FIR — served instantly from the warm case
 *  cache (no graph metrics, no cross-FIR linking — PERF-001). */
export interface CaseBasic {
  CaseMasterID: string;
  CrimeNo: string | null;
  registered_date: string | null;
  incident_from: string | null;
  subhead_name: string | null;
  head_name: string | null;
  category: string | null;
  gravity: string | null;
  status: string | null;
  station_name: string | null;
  district_name: string | null;
  accused: CasePerson[];
  victims: CasePerson[];
  narrative: string | null;
}

/** Fetch the basic detail for one case (the graph's case-click panel). */
export function fetchCaseBasic(caseId: string): Promise<{ case: CaseBasic }> {
  return get(`/api/cases/${encodeURIComponent(caseId)}`);
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
  seed: {
    case_id: string;
    subhead: string;
    station: string;
    district: string;
    // attribute ids + primary-accused profile — used to pre-apply the seed's
    // attributes (crime type, district, suspect age/gender/name) as filters on expand
    subhead_id: string;
    district_id: string;
    station_id: string;
    accused_name: string | null;
    accused_age: number | null;
    accused_gender: string | null;
  } | null;
  focus: string | null;
  channel: string | null;
  /** cases on THIS page (association_count) out of total_matches for the focus. */
  association_count: number;
  total_matches: number;
  offset: number;
  /** always 0 on the overview — it computes no related-case universe (PERF-001). */
  total_related: number;
  /** node_id -> expandable flag (1 = has more to reveal). No counts (PERF-001);
   *  the number type is kept so the `> 0` expand gates read unchanged. */
  expandable: Record<string, number>;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** Investigative association search for a seed case (same-suspect + shared
 *  entities), with server-side attribute filters (orthogonal to the View).
 *
 *  focus omitted  -> the overview: the seed case + its own entities, each
 *                    flagged `expandable` (no counts — PERF-001).
 *  focus="TYPE:id" -> expand that one entity into its related cases (to merge
 *                    into the current graph). */
export function fetchAssociations(
  caseId: string,
  filters: AssocFilters = {},
  focus?: string,
  page?: { limit: number; offset: number },
): Promise<AssociationResult> {
  const p = new URLSearchParams({ case_id: caseId });
  if (focus) p.set("focus", focus);
  if (page) {
    p.set("limit", String(page.limit));
    p.set("offset", String(page.offset));
  }
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  }
  return get(`/api/associations?${p}`);
}

/** One case a person is named on — a light FIR restatement (no graph metrics). */
export interface PersonCase {
  case_id: string;
  crime_no: string | null;
  subhead_name: string | null;
  district_name: string | null;
  registered_date: string | null;
  status: string | null;
}

/** A clicked accused/victim: their own attributes (FACT) plus the cases sharing
 *  the exact same name+age+gender (a POTENTIAL_ASSOCIATION — namesakes possible). */
export interface PersonDetail {
  role: "accused" | "victim";
  record_id: string;
  name: string | null;
  age: number | null;
  gender: string | null;
  district_id: string | null;
  district_name: string | null;
  case_count: number;
  cases: PersonCase[];
}

/** Fetch one accused/victim's detail + their other cases (the person-click panel). */
export function fetchPerson(
  role: "accused" | "victim",
  recordId: string,
): Promise<{ person: PersonDetail }> {
  return get(`/api/persons/${role}/${encodeURIComponent(recordId)}`);
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
