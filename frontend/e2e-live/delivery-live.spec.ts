import fs from "node:fs";
import { expect, test } from "@playwright/test";

type E2EState = {
  token: string;
  cross_tenant_token: string;
  sprint_id: string;
  evidence_id: string;
};

const statePath = process.env.E2E_STATE_PATH;
if (!statePath) throw new Error("E2E_STATE_PATH is required");
const state = JSON.parse(fs.readFileSync(statePath, "utf8")) as E2EState;
const apiBase = process.env.VITE_API_URL || "http://127.0.0.1:8000";

test.beforeEach(async ({ page }) => {
  await page.addInitScript((token) => {
    window.sessionStorage.setItem("e2e_access_token", token);
  }, state.token);
});

test("persisted sprint evidence becomes a review-only intervention with audit continuity", async ({ page }) => {
  await page.goto("/command-center");
  await expect(page.getByRole("heading", { name: /Good evening/ })).toBeVisible();
  await expect(page.getByText("Identity provider").first()).toBeVisible();
  await expect(page.getByText(/persisted projects/i)).toBeVisible();

  await page.goto("/my-day");
  await expect(page.getByRole("heading", { name: "My Day" })).toBeVisible();
  await expect(page.getByText("Authentication API").first()).toBeVisible();

  await page.goto("/sprints");
  await expect(page.getByRole("heading", { name: "Sprint Intelligence" })).toBeVisible();
  await page.getByRole("link", { name: "Live Sprint 24" }).click();
  await expect(page.getByRole("heading", { name: "Live Sprint 24" })).toBeVisible();
  await expect(page.getByText("Authentication API").first()).toBeVisible();

  await page.getByRole("button", { name: "Ask Axiom about this sprint" }).click();
  await expect(page.getByText("Identity provider delivery delayed")).toBeVisible();
  await expect(page.getByText(/Primary risk: Authentication API/)).toBeVisible();
  await page.getByRole("button", { name: "Open evidence" }).click();
  await expect(page.getByRole("dialog", { name: "Evidence detail" })).toContainText("missed its committed delivery date");

  const proposalResponsePromise = page.waitForResponse((response) =>
    response.url().endsWith("/api/delivery/proposed-actions") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Save proposed intervention" }).click();
  const proposalResponse = await proposalResponsePromise;
  expect(proposalResponse.status()).toBe(201);
  const proposal = await proposalResponse.json();
  await expect(page.getByText(/Draft saved for human review/)).toBeVisible();
  await expect(page.getByText(/Audit trail verified: 8 correlated events/)).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "Live Sprint 24" })).toBeVisible();
  const persisted = await page.request.get(
    `${apiBase}/api/delivery/proposed-actions/${proposal.id}`,
    { headers: { Authorization: `Bearer ${state.token}` } },
  );
  expect(persisted.status()).toBe(200);
  expect((await persisted.json()).evidence_ids).toContain(state.evidence_id);
});

test("cross-tenant signed identity cannot read the persisted sprint or its evidence", async ({ request }) => {
  const headers = { Authorization: `Bearer ${state.cross_tenant_token}` };
  const sprint = await request.get(`${apiBase}/api/sprints/${state.sprint_id}`, { headers });
  const evidence = await request.get(`${apiBase}/api/delivery/evidence/${state.evidence_id}`, { headers });
  expect(sprint.status()).toBe(404);
  expect(evidence.status()).toBe(404);
});
