/**
 * Typed client for the KAVACH analytics API (LOCAL synthetic-data path).
 * Base URL points at the local FastAPI backend (port 8001). CORS on the
 * backend already allows the Vite dev origin (:5173). All data is SYNTHETIC.
 */

export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://127.0.0.1:8001";

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
  station_name: string | null;
  hour_histogram: number[]; // 24 bins, index = hour of day
  night_share: number; // fraction of cases in the 21:00–02:00 window
  sample_case_ids: string[];
}

export interface HotspotsResponse {
  synthetic: boolean;
  params: Record<string, unknown>;
  cluster_count: number;
  clustered_cases: number;
  noise_cases: number;
  hotspots: Hotspot[];
}

/** Common filter state shared by the /cases and /hotspots queries. */
export interface Filters {
  subheadId: string | null; // crime sub-head id, null = all
  days: number | null; // recency window, null = full range
}

async function getJSON<T>(path: string, params: Record<string, unknown> = {}): Promise<T> {
  const url = new URL(API_BASE + path);
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== "") url.searchParams.set(k, String(v));
  }
  const res = await fetch(url.toString());
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
    date_from: daysToDateFrom(f.days, latest),
    with_coords: true,
    limit: 5000,
  });

export const fetchHotspots = (f: Filters, epsM = 400, minSamples = 8) =>
  getJSON<HotspotsResponse>("/api/hotspots", {
    subhead_id: f.subheadId,
    days: f.days,
    eps_m: epsM,
    min_samples: minSamples,
  });
