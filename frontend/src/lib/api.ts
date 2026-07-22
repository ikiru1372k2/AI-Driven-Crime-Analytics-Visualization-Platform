/**
 * Typed client for the KAVACH analytics API (LOCAL synthetic-data path).
 * Base URL points at the local FastAPI backend (port 8000). CORS on the
 * backend already allows the Vite dev origin (:5173). All data is SYNTHETIC.
 */

const configuredBase = import.meta.env.VITE_API_BASE as string | undefined;

/** Where API calls go.
 *
 *  - unset            -> the local FastAPI dev server (Vite dev path)
 *  - "" (empty)       -> RELATIVE, i.e. same origin as the page. The deployed
 *                        build uses this: AppSail serves the console and the
 *                        API together, which avoids CORS entirely.
 *  - an absolute URL  -> that origin (e.g. a gateway base). */
export const API_BASE = configuredBase === undefined ? "http://127.0.0.1:8000" : configuredBase;

export interface CrimeSubHead {
  subhead_id: string;
  subhead_name: string;
  head_id: string;
  head_name: string;
}

export interface District {
  district_id: string;
  district_name: string;
}

export interface Station {
  station_id: string;
  station_name: string;
  district_id: string;
}

export interface Meta {
  synthetic: boolean;
  total_cases: number;
  cases_with_coords: number;
  date_range: { from: string | null; to: string | null };
  map_center: { lat: number; lon: number };
  crime_subheads: CrimeSubHead[];
  districts: District[];
  stations: Station[];
  statuses: string[];
}

export interface CaseRecord {
  CaseMasterID: string;
  CrimeNo: string;
  registered_date: string | null;
  incident_from: string | null;
  latitude: number | null;
  longitude: number | null;
  subhead_id: string;
  subhead_name: string;
  head_id: string;
  head_name: string;
  category: string | null;
  gravity: string | null;
  status: string | null;
  station_id: string;
  station_name: string;
  district_id: string;
  district_name: string;
}

export interface CasesResponse {
  synthetic: boolean;
  count: number;
  cases: CaseRecord[];
}

export interface Hotspot {
  rank: number;
  case_count: number;
  center: { lat: number; lon: number };
  radius_m: number;
  top_crime: string | null;
  crime_breakdown: Record<string, number>;
  district_name: string | null;
  station_id: string | null;
  station_name: string | null;
  hour_histogram: number[]; // 24 bins, index = hour of day
  night_share: number; // fraction of cases in the 21:00–02:00 window
  sample_case_ids: string[];
  case_ids: string[]; // full cluster membership (for case drill-down)
}

export interface HotspotsResponse {
  synthetic: boolean;
  params: Record<string, unknown>;
  cluster_count: number;
  clustered_cases: number;
  noise_cases: number;
  hotspots: Hotspot[];
}

/** Common filter state shared by the /cases, /hotspots and /trends queries. */
export interface Filters {
  subheadId: string | null; // crime sub-head id, null = all
  districtId: string | null; // district id, null = whole state
  days: number | null; // recency window, null = full range
}

/**
 * Local dev only: the API's graph/evidence routes are behind Catalyst auth, so
 * send a seeded dev identity (see backend demo_users) to resolve a role + scope.
 * Never emitted in production builds — there the Catalyst session supplies the
 * real auth headers, and the backend only honours this header when
 * KAVACH_DEV_AUTH=1 in a non-Catalyst runtime.
 */
export const DEV_AUTH_HEADERS: Record<string, string> = import.meta.env.DEV
  ? { "x-kavach-dev-user": (import.meta.env.VITE_DEV_USER as string) || "demo-state-analyst" }
  : {};

async function getJSON<T>(path: string, params: Record<string, unknown> = {}): Promise<T> {
  // second arg matters when API_BASE is "" (same-origin deployment): a bare
  // "/api/…" is not a valid absolute URL on its own
  const url = new URL(API_BASE + path, window.location.origin);
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== "") url.searchParams.set(k, String(v));
  }
  const res = await fetch(url.toString(), { headers: DEV_AUTH_HEADERS });
  if (!res.ok) throw new Error(`${path} → ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const fetchMeta = () => getJSON<Meta>("/api/meta");

/**
 * The /cases endpoint filters by explicit date_from (not a `days` window like
 * /hotspots does), so callers resolve the recency window to a YYYY-MM-DD date
 * against the dataset's latest case — keeping the map points and the hotspot
 * clusters over the same time span.
 */
export function daysToDateFrom(days: number | null, latest: string | null): string | null {
  if (days === null || !latest) return null;
  const d = new Date(latest + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

export const fetchCases = (f: Filters, latest: string | null) =>
  getJSON<CasesResponse>("/api/cases", {
    subhead_id: f.subheadId,
    district_id: f.districtId,
    date_from: daysToDateFrom(f.days, latest),
    with_coords: true,
    limit: 5000,
  });

export const fetchHotspots = (f: Filters, epsM = 400, minSamples = 8) =>
  getJSON<HotspotsResponse>("/api/hotspots", {
    subhead_id: f.subheadId,
    district_id: f.districtId,
    days: f.days,
    eps_m: epsM,
    min_samples: minSamples,
  });

// --- trends / alerts (Phase 4) ---

export type Severity = "critical" | "serious" | "warning" | null;

export interface TrendAlert {
  rank: number;
  level: "station" | "subhead";
  subhead_id: string;
  subhead_name: string;
  station_id: string | null;
  station_name: string | null;
  district_name: string | null;
  z_score: number;
  severity: Severity;
  direction: "up" | "down";
  recent_count: number;
  recent_weekly: number;
  baseline_weekly_median: number;
  baseline_mad: number;
  pct_change: number | null;
  window: { from: string; to: string };
  weekly_series: number[]; // oldest -> newest
  sample_case_ids: string[];
}

export interface TrendsResponse {
  synthetic: boolean;
  params: Record<string, unknown>;
  alert_count: number;
  alerts: TrendAlert[];
}

export interface Overview {
  synthetic: boolean;
  total_cases: number;
  date_range: { from: string | null; to: string | null };
  map_center: { lat: number; lon: number };
  alert_tally: { critical: number; serious: number; warning: number };
  top_trends: TrendAlert[];
  top_hotspots: Hotspot[];
  hotspot_count: number;
}

export const fetchTrends = (
  f: Filters,
  level: "station" | "subhead" = "station",
  minZ = 2.5,
) =>
  getJSON<TrendsResponse>("/api/trends", {
    level,
    subhead_id: f.subheadId,
    district_id: f.districtId,
    min_z: minZ,
  });

export const fetchOverview = () => getJSON<Overview>("/api/overview");

// --- district choropleth (case velocity) ---

export interface DistrictStat {
  district_id: string;
  district_name: string;
  case_count: number;
  cases_with_coords: number;
  recent_count: number;
  prior_count: number;
  velocity: number | null; // recent vs prior window ratio; >1 = rising
}

export interface DistrictsResponse {
  synthetic: boolean;
  window_days: number;
  districts: DistrictStat[];
}

export const fetchDistricts = () => getJSON<DistrictsResponse>("/api/districts");

// --- area-risk forecast (FORECAST tab, live QuickML) ---

export type RiskLevel = "High" | "Medium" | "Low";

export interface RiskDistrict {
  rank: number;
  district_id: string;
  district_name: string;
  risk_level: RiskLevel;
  expected_count: number; // QuickML forecast for the next window
  recent_count: number; // cases in the last window (baseline)
  trend: "up" | "down" | "flat";
  forecast_pct_change: number; // forecast vs recent, %
  drivers: string[]; // plain-English computed facts
  summary: string; // one-sentence plain-English read-out
  summary_source: string; // "template" or the LLM model id (e.g. qwen-2.5-14b-instruct)
  confidence: { level: "high" | "medium" | "low"; basis: string };
  sample_case_ids: string[]; // recent FIRs behind this forecast (evidence trail)
}

export interface IntelligenceEnvelope {
  classification: string;
  classification_label: string;
  method: { method_name: string; method_version: string; model_version?: string };
  limitations?: string[];
}

export interface RiskResponse {
  synthetic: boolean;
  available: boolean; // false => QuickML unconfigured/unreachable (no numbers shown)
  reason?: string; // why unavailable
  window_days: number;
  model_version: string;
  district_count?: number;
  districts: RiskDistrict[];
  intelligence: IntelligenceEnvelope;
}

export const fetchRisk = (windowDays = 30) =>
  getJSON<RiskResponse>("/api/risk", { window_days: windowDays });

// --- entity resolution (identity candidates) ---

export interface IdentityMember {
  accused_id: string;
  case_id: string;
  name: string;
  age: number | null;
  gender: string | null;
  district_id: string | null;
  district_name: string | null;
}

export interface IdentitySignal {
  a: string;
  b: string;
  score: number;
  name_sim: number;
  age_gap: number | null;
  contributing: string[];
  contradictory: string[];
  linked: boolean;
}

export interface IdentityCandidate {
  cluster_id: string;
  size: number;
  confidence: number;
  status: string;
  gender: string | null;
  name_variants: string[];
  age_range: [number, number] | null;
  districts: string[];
  members?: IdentityMember[];
  signals?: IdentitySignal[];
}

export interface IdentitiesResponse {
  synthetic: boolean;
  params: Record<string, unknown>;
  accused_total: number;
  pairs_scored: number;
  candidate_count: number;
  candidates: IdentityCandidate[];
}

/** Review queue. The list omits per-candidate evidence (members/signals) —
 *  that is 88% of the payload (1.1 MB for 512 candidates) and is only needed
 *  for the row an analyst expands, which fetchIdentityDetail supplies. */
export const fetchIdentities = () => getJSON<IdentitiesResponse>("/api/identities");

export const fetchIdentityDetail = (clusterId: string) =>
  getJSON<IdentityCandidate>(`/api/identities/${encodeURIComponent(clusterId)}`);
