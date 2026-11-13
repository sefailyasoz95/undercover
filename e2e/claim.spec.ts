import { expect, test, type APIRequestContext } from "@playwright/test";

async function decide(
  request: APIRequestContext,
  claimId: string,
  decision: string,
  payout: number,
) {
  await request.post(`/api/claims/${claimId}/start`);
  await request.post(`/api/claims/${claimId}/steps`, {
    data: { kind: "tool", content: "get_claim({})" },
  });
  await request.post(`/api/claims/${claimId}/steps`, {
    data: { kind: "reply", content: `Decided ${claimId}.` },
  });
  const response = await request.post(`/api/claims/${claimId}/decision`, {
    data: {
      decision,
      payout,
      reasons: "The documents support the claim and the policy covers it.",
      policy_section: "Section 7, Emergency Medical",
    },
  });
  expect(response.ok()).toBe(true);
}

test("a claim shows the agent's steps and decision", async ({
  page,
  request,
}) => {
  await decide(request, "CLM-1013", "decline", 0);
  await page.goto("/#/claims/CLM-1013");
  await expect(page.getByText("Declined $0.00")).toBeVisible();
  await expect(
    page.getByText("The documents support the claim and the policy covers it."),
  ).toBeVisible();
  await expect(page.getByText("get_claim({})")).toBeVisible();
  await expect(page.getByText("Decided CLM-1013.")).toBeVisible();
});

test("a payout over the limit waits for a handler's sign-off", async ({
  page,
  request,
}) => {
  await decide(request, "CLM-1016", "approve", 6200);

  const payment = await request.post("/api/claims/CLM-1016/payment", {
    data: { amount: 6200 },
  });
  expect(payment.status()).toBe(409);

  await page.goto("/");
  const row = page.getByRole("row", { name: /CLM-1016/ });
  await expect(row.getByText("Waiting for sign-off")).toBeVisible();
  await row.getByRole("link", { name: "CLM-1016" }).click();

  await expect(page.getByText(/held until a handler signs off/)).toBeVisible();
  await expect(page.getByText("Not paid yet.")).toBeVisible();
  await page.getByRole("combobox").selectOption({ label: "Dana Whitfield" });
  await page.getByRole("button", { name: "Sign off and pay" }).click();

  await expect(page.getByText(/signed off by Dana Whitfield/)).toBeVisible();
  await expect(page.getByText("Decided", { exact: true })).toBeVisible();
});
