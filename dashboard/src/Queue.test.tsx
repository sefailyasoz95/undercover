import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { fakeApi, summary } from "./fakeApi";
import { Queue } from "./Queue";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const decided = {
  ...summary,
  claim_id: "CLM-1002",
  customer_name: "Tom Reyes",
  amount_claimed: 1250,
  status: "decided",
  decision: {
    decision: "approve",
    payout: 1250,
    reasons: "Covered.",
    policy_section: "Section 5",
    decided_at: "2026-11-13",
  },
};

it("lists the claims with their states and a count for each state", async () => {
  fakeApi({ "GET /api/claims": [summary, decided] });
  render(<Queue />);
  const link = await screen.findByRole("link", { name: "CLM-1001" });
  expect(link.getAttribute("href")).toBe("#/claims/CLM-1001");
  expect(screen.getByText("Maya Patel")).toBeDefined();
  expect(screen.getAllByText("Trip delay")).toHaveLength(2);
  expect(screen.getByText("$1,250.00")).toBeDefined();
  expect(screen.getByText("Approved $1,250.00")).toBeDefined();
  const counts = within(screen.getByRole("list", { name: "Claims by state" }));
  expect(counts.getAllByText("1")).toHaveLength(2);
  expect(counts.getAllByText("0")).toHaveLength(2);
});

it("works the queue", async () => {
  const fetchMock = fakeApi({
    "GET /api/claims": [summary],
    "POST /api/queue/run": { claim_ids: ["CLM-1001"] },
  });
  render(<Queue />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Work the queue" }),
  );
  expect(
    await screen.findByText("The agent is working through 1 claims."),
  ).toBeDefined();
  expect(fetchMock).toHaveBeenCalledWith("/api/queue/run", expect.anything());
});

it("has nothing to work when no claim is waiting", async () => {
  fakeApi({ "GET /api/claims": [decided] });
  render(<Queue />);
  const button = await screen.findByRole("button", { name: "Work the queue" });
  expect((button as HTMLButtonElement).disabled).toBe(true);
});

it("refreshes the queue", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const fetchMock = fakeApi({ "GET /api/claims": [summary] });
  render(<Queue />);
  await screen.findByText("Maya Patel");
  await vi.advanceTimersByTimeAsync(3000);
  expect(fetchMock.mock.calls.length).toBeGreaterThan(1);
  vi.useRealTimers();
});

it("says when the backend is down", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<Queue />);
  expect(
    await screen.findByText("The backend is not responding."),
  ).toBeDefined();
});
