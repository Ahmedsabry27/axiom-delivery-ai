import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const agent = {
  id: "agent-e2e-1", tenant_id: "e2e-tenant", slug: "deployment-reporter",
  name: "Deployment Reporter", description: "Creates governed deployment reports",
  owner_id: "owner-e2e", lifecycle_status: "enabled", operational_health: "healthy",
  current_version: 3, published_version: 2, lock_version: 7,
  model: "gpt-5", model_provider: "openai", model_configuration: { provider: "openai", model: "gpt-5" },
  planner_configuration: { name: "react" }, memory_configuration: {}, execution_limits: { max_steps: 20 },
  tool_discovery_configuration: { mode: "assigned_only" }, capabilities: ["deployment-report"],
  environment_restrictions: ["e2e"], tool_count: 1, knowledge_count: 1,
  execution_count: 4, success_rate: 75, last_execution_at: "2026-08-03T12:00:00Z",
  created_at: "2026-08-01T12:00:00Z", updated_at: "2026-08-03T12:00:00Z",
  instructions: "Create safe reports.", permissions: { publish: true, enable: true, disable: true, archive: true, restore: false },
};

async function installApi(page: Page) {
  const failures: string[] = [];
  const consoleErrors: string[] = [];
  page.on("requestfailed", request => failures.push(`${request.method()} ${request.url()}`));
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await page.addInitScript(() => sessionStorage.setItem("e2e_access_token", "signed-test-token-redacted"));
  await page.route("**/api/delivery/metadata", route => route.fulfill({
    json: { workspace: { is_demo: false }, portfolios: [], programmes: [], projects: [], teams: [] },
  }));
  await page.route("**/api/v1/agents**", async route => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/v1/agents") {
      const filtered = url.searchParams.get("search") === "missing" ? [] : [agent];
      return route.fulfill({ json: { items: filtered, total: filtered.length, page: 1, page_size: 20, pages: filtered.length ? 1 : 0, permissions: { create: true } } });
    }
    if (url.pathname.endsWith("/analytics")) return route.fulfill({ json: { total_executions: 4, succeeded: 3, failed: 1, cancelled: 0, timed_out: 0, success_rate: 75, timeout_rate: 0, average_duration_ms: 420, estimated_cost: 0.04, actual_cost: 0.03, currency: "USD", input_required: 1, clarification_required: 1, approval_required: 1, tool_usage: [{ name: "deployment_report", executions: 3, succeeded: 3 }] } });
    if (url.pathname.endsWith("/activity")) return route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 25, pages: 0 } });
    if (url.pathname.endsWith("/versions")) return route.fulfill({ json: [] });
    if (/\/executions$/.test(url.pathname)) return route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 25, pages: 0 } });
    if (/\/(tools|knowledge|access)$/.test(url.pathname)) return route.fulfill({ json: [] });
    if (route.request().method() === "GET") return route.fulfill({ json: agent });
    return route.fulfill({ json: agent });
  });
  return { failures, consoleErrors };
}

test("server-backed directory controls preserve URL state and expose an accessible empty state", async ({ page }, testInfo) => {
  const evidence = await installApi(page);
  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "Agents" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Deployment Reporter" }).first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("agents-directory.png"), fullPage: true });
  const search = page.getByRole("textbox", { name: "Search Agents" });
  await search.fill("missing");
  await expect(page).toHaveURL(/search=missing/);
  await expect(page.getByText(/no agents match/i)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("filtered-empty.png"), fullPage: true });
  expect(evidence.failures).toEqual([]);
  expect(evidence.consoleErrors).toEqual([]);
});

test("workspace navigation and overview analytics use API data", async ({ page }, testInfo) => {
  const evidence = await installApi(page);
  await page.goto(`/agents/${agent.id}/overview`);
  await expect(page.getByRole("heading", { name: agent.name })).toBeVisible();
  const overview = page.getByRole("link", { name: "Overview" });
  await expect(overview).toHaveAttribute("aria-current", "page");
  await page.getByRole("link", { name: "Configuration" }).click();
  await expect(page).toHaveURL(new RegExp(`/agents/${agent.id}/configuration$`));
  await overview.click();
  await expect(page).toHaveURL(new RegExp(`/agents/${agent.id}/overview$`));
  await expect(page.getByText("75%", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("agent-analytics.png"), fullPage: true });
  const results = await new AxeBuilder({ page }).disableRules(["color-contrast"]).analyze();
  expect(results.violations.filter(item => ["critical", "serious"].includes(item.impact || ""))).toEqual([]);
  expect(evidence.failures).toEqual([]);
  expect(evidence.consoleErrors).toEqual([]);
});
