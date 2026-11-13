import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Claim, Policy, Step } from "./api";
import { ClaimView } from "./ClaimView";
import { claim, fakeApi, type Routes } from "./fakeApi";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const policy: Policy = {
  policy_id: "POL-2001",
  plan: { name: "UnderCover Premium", deductible: 50 },
  add_ons: [],
  purchased_on: "2026-04-22",
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100,
  },
  travelers: ["Maya Patel"],
};

const handlers = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
  },
  { handler_id: "HND-02", name: "Marcus Oyelaran", role: "Claims Handler" },
];

const steps: Step[] = [
  { id: 1, kind: "tool", content: "get_claim({})", created_at: "" },
  { id: 2, kind: "result", content: "get_claim: {}", created_at: "" },
  { id: 3, kind: "reply", content: "Approved $1,500.00.", created_at: "" },
];

const approved = (payout: number) => ({
  decision: "approve" as const,
  payout,
  reasons: "The bag was stolen and the police report supports it.",
  policy_section: "Section 5, Baggage and Personal Effects",
  decided_at: "2026-11-13T10:00:00+00:00",
});

function show(found: Claim, extra: Routes = {}) {
  const fetchMock = fakeApi({
    "GET /api/claims/CLM-1001": found,
    "GET /api/claims/CLM-1001/steps": [],
    "GET /api/policies/POL-2001": policy,
    "GET /api/handlers": handlers,
    ...extra,
  });
  render(<ClaimView claimId="CLM-1001" />);
  return fetchMock;
}

it("shows the claim and its policy", async () => {
  show(claim);
  expect(await screen.findByText(claim.story)).toBeDefined();
  expect(screen.getByText("Airport hotel")).toBeDefined();
  expect(screen.getByText("Hotel receipt")).toBeDefined();
  expect(await screen.findByText("UnderCover Premium")).toBeDefined();
  expect(screen.getByText("No steps yet.")).toBeDefined();
});

it("runs the agent on a waiting claim", async () => {
  const fetchMock = show(claim, {
    "POST /api/claims/CLM-1001/run": { status: "started" },
  });
  fireEvent.click(await screen.findByRole("button", { name: "Run agent" }));
  await vi.waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/claims/CLM-1001/run",
      expect.anything(),
    );
  });
});

it("shows a decided claim with its decision and payment", async () => {
  show({
    ...claim,
    status: "decided",
    decision: approved(420),
    payment: { amount: 420, paid_at: "2026-11-13T10:00:01+00:00" },
  });
  expect(await screen.findByText("Approved $420.00")).toBeDefined();
  expect(screen.getByText(approved(420).reasons)).toBeDefined();
  expect(screen.getByText(approved(420).policy_section)).toBeDefined();
  expect(screen.getByText(/on 2026-11-13/)).toBeDefined();
  expect(screen.queryByRole("button", { name: "Run agent" })).toBeNull();
});

it("shows an approval that has not been paid", async () => {
  show({ ...claim, status: "decided", decision: approved(420) });
  expect(await screen.findByText("Not paid yet.")).toBeDefined();
});

it("shows new steps while the agent works", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const working = { ...claim, status: "in_progress" as const };
  const fetchMock = show(working);
  expect(
    await screen.findByText("The agent is working on this claim."),
  ).toBeDefined();
  fetchMock.mockImplementation((path: string) =>
    Promise.resolve(
      new Response(JSON.stringify(path.endsWith("/steps") ? steps : working)),
    ),
  );
  await vi.advanceTimersByTimeAsync(2000);
  expect(await screen.findByText("get_claim({})")).toBeDefined();
  expect(screen.getByText("Approved $1,500.00.")).toBeDefined();
});

it("signs off a payout over the limit", async () => {
  const held = {
    ...claim,
    status: "awaiting_signoff" as const,
    decision: approved(1500),
  };
  const fetchMock = show(held, {
    "POST /api/claims/CLM-1001/signoff": {
      ...held,
      status: "decided",
      signoff: {
        handler_id: "HND-02",
        name: "Marcus Oyelaran",
        signed_off_at: "",
      },
      payment: { amount: 1500, paid_at: "2026-11-13T11:00:00+00:00" },
    },
  });
  expect(
    await screen.findByText(/is held until a handler signs off/),
  ).toBeDefined();
  await screen.findByRole("option", { name: "Marcus Oyelaran" });
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: "HND-02" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign off and pay" }));
  expect(
    await screen.findByText(/signed off by Marcus Oyelaran/),
  ).toBeDefined();
  expect(screen.getByText("Decided")).toBeDefined();
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/claims/CLM-1001/signoff",
    expect.objectContaining({ body: JSON.stringify({ handler_id: "HND-02" }) }),
  );
});

it("says when a claim cannot be found", async () => {
  fakeApi({});
  render(<ClaimView claimId="CLM-1001" />);
  expect(await screen.findByText(/could not be loaded/)).toBeDefined();
});
