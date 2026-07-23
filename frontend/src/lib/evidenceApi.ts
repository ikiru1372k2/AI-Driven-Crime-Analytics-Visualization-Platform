/**
 * Client for persisted analyst decisions (identity merges + alert acks).
 * Shared by the Identities review and the Trends overview — any AI output the
 * analyst adjudicates is recorded through this decision API and read back here.
 */
import { API_BASE, DEV_AUTH_HEADERS } from "./api";

export interface DecisionState {
  target_ref: string;
  kind: "ALERT_ACK" | "IDENTITY";
  decision: string;
  actor_id: string;
  decided_at: string;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: DEV_AUTH_HEADERS });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export const fetchDecisions = () =>
  get<{ decisions: DecisionState[] }>("/api/v1/decisions");

export async function postDecision(body: {
  kind: "ALERT_ACK" | "IDENTITY";
  target_ref: string;
  decision: string;
}): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/decisions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...DEV_AUTH_HEADERS },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}
