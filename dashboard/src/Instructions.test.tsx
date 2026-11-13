import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { fakeApi } from "./fakeApi";
import { Instructions } from "./Instructions";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the instructions, read only", async () => {
  fakeApi({
    "GET /api/instructions": { text: "You are the UnderCover Agent." },
  });
  render(<Instructions />);
  expect(
    await screen.findByText("You are the UnderCover Agent."),
  ).toBeDefined();
  expect(screen.queryByRole("textbox")).toBeNull();
});
