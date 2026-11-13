import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { claim, fakeApi, summary } from "./fakeApi";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

it("shows the queue by default", async () => {
  fakeApi({ "GET /api/claims": [summary] });
  render(<App />);
  expect(
    await screen.findByRole("heading", { name: "Claims queue" }),
  ).toBeDefined();
});

it("follows the hash to the instructions and to a claim", async () => {
  fakeApi({
    "GET /api/instructions": { text: "You are the UnderCover Agent." },
    "GET /api/claims/CLM-1001": claim,
    "GET /api/claims/CLM-1001/steps": [],
    "GET /api/policies/POL-2001": null,
    "GET /api/handlers": [],
  });
  window.location.hash = "#/instructions";
  render(<App />);
  expect(
    await screen.findByText("You are the UnderCover Agent."),
  ).toBeDefined();

  act(() => {
    window.location.hash = "#/claims/CLM-1001";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
  expect(
    await screen.findByRole("heading", { name: /CLM-1001/ }),
  ).toBeDefined();
});
