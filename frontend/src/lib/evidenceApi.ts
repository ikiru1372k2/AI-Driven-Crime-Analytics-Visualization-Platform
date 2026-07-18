/**
 * Client for the Evidence & Provenance browser + persisted decisions
 * (design review 1h — any AI output → method → source FIRs → audit trail).
 */
import { API_BASE } from "./api";

export interface EvidenceRun {
  run_id: string;
  intelligence_type: string;
  method_name: string;
  method_version: string;
  model_version: string | null;
  window_from: string;
  window_to: string;
  status: "RUNNING" | "COMPLETED" | "FAILED";
  error: string | null;
  generated_at: string;
  record_count: number;
}

export interface EvidenceRow {
  result_ref: string;
  classification: string;
  evidence_case_ids: number[];
  evidence_case_total: number;
  factors: { name: string; contribution: number; direction: string }[];
  limitations: string[];
}

export interface RunDetail {
  run: EvidenceRun & { window_from: string; window_to: string };
  evidence_count: number;
  evidence: EvidenceRow[];
  evidence_truncated: number;
}

export interface DecisionState {
  target_ref: string;
  kind: "ALERT_ACK" | "IDENTITY";
  decision: string;
  actor_id: string;
  decided_at: string;
}

export interface ActivityEntry {
  text: string;
  kind: string;
  decision: string;
  when: string;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export const fetchEvidenceRuns = () =>
  get<{ runs: EvidenceRun[] }>("/api/v1/evidence/runs");

export const fetchRunDetail = (runId: string) =>
  get<RunDetail>(`/api/v1/evidence/runs/${encodeURIComponent(runId)}`);

export const fetchActivity = () =>
  get<{ activity: ActivityEntry[] }>("/api/v1/evidence/activity");

export const fetchDecisions = () =>
  get<{ decisions: DecisionState[] }>("/api/v1/decisions");

export async function postDecision(body: {
  kind: "ALERT_ACK" | "IDENTITY";
  target_ref: string;
  decision: string;
}): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/decisions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}
