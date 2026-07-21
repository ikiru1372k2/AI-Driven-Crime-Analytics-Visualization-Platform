/**
 * Client for the MO extraction API (MO-002/#38).
 * Every attribute carries a confidence and, where the narrative justified it,
 * a source_span into that narrative — which is what lets the view highlight
 * the exact phrase behind a value.
 */
import { API_BASE, DEV_AUTH_HEADERS } from "./api";
import type { IntelligenceEnvelope } from "./graphApi";

export interface MoAttribute {
  value: string | number;
  confidence: number;
  /** [start, end) into the narrative; absent when the value is UNKNOWN */
  source_span?: [number, number] | null;
}

export interface MoProfile {
  case_master_id: number;
  schema_version: string;
  extractor: "QUICKML_LLM" | "RULE_BASED" | "ZIA_TEXT_ANALYTICS";
  model_version: string;
  extracted_at: string;
  offender_count: MoAttribute;
  mobility: MoAttribute;
  approach_method: MoAttribute;
  crime_action: MoAttribute;
  target_type: MoAttribute;
  escape_direction: MoAttribute;
  time_context: MoAttribute;
  weapon_involved: MoAttribute;
}

export interface MoCase {
  case_master_id: number;
  narrative: string;
  profile: MoProfile;
  intelligence: IntelligenceEnvelope;
}

export interface MoListRow extends MoProfile {
  narrative_preview: string;
}

export interface MoRun {
  run_id: string;
  model_version: string;
  extractor: string;
  processed: number;
  skipped: number;
  failed: number;
  zia_extractions: number;
  zia_unavailable_reason: string | null;
  unknown_rates: Record<string, number>;
  profile_count: number;
  intelligence: IntelligenceEnvelope;
}

/** Attributes shown in the view, in reading order. escape_direction is
 *  display-only (the schema excludes it from similarity). */
export const MO_FIELDS: { key: keyof MoProfile; label: string }[] = [
  { key: "crime_action", label: "Action" },
  { key: "target_type", label: "Target" },
  { key: "mobility", label: "Mobility" },
  { key: "approach_method", label: "Approach" },
  { key: "offender_count", label: "Offenders" },
  { key: "weapon_involved", label: "Weapon" },
  { key: "time_context", label: "Time" },
  { key: "escape_direction", label: "Escape" },
];

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: DEV_AUTH_HEADERS });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const fetchMoRun = () => get<MoRun>("/api/v1/mo/runs/latest");

export interface MoPage {
  total: number;
  offset: number;
  limit: number;
  count: number;
  profiles: MoListRow[];
}

/** Search + page server-side: only one page crosses the wire, so the client
 *  never holds the whole corpus (see the scaling note in moRoutes). */
export const fetchMoProfiles = (opts: {
  q?: string;
  action?: string;
  target?: string;
  limit?: number;
  offset?: number;
} = {}) => {
  const p = new URLSearchParams();
  if (opts.q) p.set("q", opts.q);
  if (opts.action) p.set("action", opts.action);
  if (opts.target) p.set("target", opts.target);
  p.set("limit", String(opts.limit ?? 40));
  p.set("offset", String(opts.offset ?? 0));
  return get<MoPage>(`/api/v1/mo/profiles?${p}`);
};

export interface MoMatch {
  case_master_id: number;
  score: number;
  matched: string[];
  differed: string[];
  explanation: string;
  narrative_preview: string;
}

export const fetchRelated = (caseId: number, limit = 15) =>
  get<{ case_master_id: number; match_count: number; matches: MoMatch[] }>(
    `/api/v1/mo/${caseId}/related?limit=${limit}`,
  );

export const fetchMoCase = (caseId: number) => get<MoCase>(`/api/v1/mo/${caseId}`);
