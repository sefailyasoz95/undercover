export type Status = "waiting" | "in_progress" | "awaiting_signoff" | "decided";

export interface Decision {
  decision: "approve" | "decline" | "refer";
  payout: number;
  reasons: string;
  policy_section: string;
  decided_at: string;
}

export interface ClaimSummary {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  submitted_on: string;
  amount_claimed: number;
  status: Status;
  decision: Decision | null;
}

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  items: Item[];
  amount_claimed: number;
  documents: ClaimDocument[];
  status: Status;
  decision: Decision | null;
  signoff: { handler_id: string; name: string; signed_off_at: string } | null;
  payment: { amount: number; paid_at: string } | null;
}

export interface Policy {
  policy_id: string;
  plan: { name: string; deductible: number };
  add_ons: { add_on: string; name: string }[];
  purchased_on: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
}

export interface Step {
  id: number;
  kind: "tool" | "result" | "reply";
  content: string;
  created_at: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body = (await response.json()) as { detail: string };
    throw new Error(body.detail);
  }
  return (await response.json()) as T;
}

function post<T>(path: string, body: object): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const api = {
  claims: () => request<ClaimSummary[]>("/api/claims"),
  claim: (id: string) => request<Claim>(`/api/claims/${id}`),
  policy: (id: string) => request<Policy>(`/api/policies/${id}`),
  steps: (id: string) => request<Step[]>(`/api/claims/${id}/steps`),
  handlers: () => request<Handler[]>("/api/handlers"),
  instructions: () => request<{ text: string }>("/api/instructions"),
  runAgent: (id: string) =>
    post<{ status: string }>(`/api/claims/${id}/run`, {}),
  runQueue: () => post<{ claim_ids: string[] }>("/api/queue/run", {}),
  signOff: (id: string, handlerId: string) =>
    post<Claim>(`/api/claims/${id}/signoff`, { handler_id: handlerId }),
};
