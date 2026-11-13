import { expect, it } from "vitest";
import { label, money } from "./format";

it("shows money in US dollars", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(money(0)).toBe("$0.00");
});

it("turns codes into labels", () => {
  expect(label("emergency_medical")).toBe("Emergency medical");
});
