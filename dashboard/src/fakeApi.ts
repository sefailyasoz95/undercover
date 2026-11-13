import { vi } from "vitest";
import type { Claim, ClaimSummary } from "./api";

export type Routes = Record<string, unknown>;

export function fakeApi(routes: Routes) {
  const fetchMock = vi.fn((path: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${path}`;
    if (!(key in routes)) {
      return Promise.resolve(
        new Response(JSON.stringify({ detail: `${key} not found` }), {
          status: 404,
        }),
      );
    }
    return Promise.resolve(new Response(JSON.stringify(routes[key])));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export const summary: ClaimSummary = {
  claim_id: "CLM-1001",
  customer_name: "Maya Patel",
  claim_type: "trip_delay",
  summary: "Flight home canceled",
  submitted_on: "2026-06-24",
  amount_claimed: 420,
  status: "waiting",
  decision: null,
};

export const claim: Claim = {
  claim_id: "CLM-1001",
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  claim_type: "trip_delay",
  submitted_on: "2026-06-24",
  incident_date: "2026-06-18",
  incident_location: "Rome, Italy",
  summary: "Flight home canceled",
  story: "My flight home from Rome was canceled.",
  items: [
    { description: "Airport hotel", category: "accommodation", amount: 245 },
  ],
  amount_claimed: 245,
  documents: [
    { name: "Hotel receipt", type: "receipt", content: "Total paid: $245.00." },
  ],
  status: "waiting",
  decision: null,
  signoff: null,
  payment: null,
};
