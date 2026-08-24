import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const item = {
  id: "dep-18", reference: "D-018", name: "Customer API delivery",
  description: "Synthetic provider delivery for human review.", dependencyType: "TECHNICAL",
  relationshipType: "DEPENDS_ON", status: "BLOCKED", impact: "CRITICAL",
  health: { score: 35, status: "RED", dataCompleteness: 1, limitations: [], definitionVersion: "dependency-health-v1" },
  priority: { score: 100, band: "CRITICAL", triggeredFactors: [{ factor: "Currently blocked", points: 25 }], affectedEntities: ["SPRINT:s24", "RELEASE:r4"], ruleVersion: "dependency-priority-v1" },
  ownerId: "owner-1", providerOwnerId: "provider-1",
  provider: { key: "SYSTEM:customer-api", entityType: "SYSTEM", entityId: "customer-api", name: "Customer API" },
  consumer: { key: "WORK_ITEM:mobile", entityType: "WORK_ITEM", entityId: "mobile", name: "Mobile App" },
  requiredByDate: "2026-08-18", committedResolutionDate: "2026-08-19", forecastResolutionDate: "2026-08-23",
  identifiedAt: "2026-08-01T00:00:00Z", blockedSince: "2026-08-12T00:00:00Z", criticalPath: true,
  external: true, sourceSystem: "MANUAL", projectId: "project-1", ageDays: 14, evidenceCount: 1,
  downstreamCount: 2, version: 1, updatedAt: "2026-08-15T00:00:00Z",
};

async function installDependencyApi(page: Page) {
  const proposals: Array<Record<string, string>> = [];
  const scenarios: Array<Record<string, unknown>> = [];
  await page.addInitScript(() => sessionStorage.setItem("e2e_access_token", "signed-test-token-redacted"));
  await page.route("**/api/dependencies**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (request.method() === "POST" && path === "/api/dependencies") {
      return route.fulfill({ status: 409, json: { detail: "Cycle detected: RELEASE:r4 → SYSTEM:customer-api → RELEASE:r4" } });
    }
    if (request.method() === "POST" && path.endsWith("/proposals")) {
      const proposal = { id: "proposal-1", actionType: "DRAFT_ESCALATION", content: "Escalate D-018 to the provider owner.", status: "PROPOSED", createdAt: "2026-08-15T10:00:00Z" };
      proposals.splice(0, proposals.length, proposal);
      return route.fulfill({ status: 201, json: { item: proposal, externalWrites: false } });
    }
    if (request.method() === "POST" && path === "/api/dependencies/graph/scenarios") {
      const result = { id: "scenario-1", changeValue: { days: 5 }, scenarioResult: { directlyAffectedEntities: ["WORK_ITEM:mobile"], indirectlyAffectedEntities: ["SPRINT:s24", "MILESTONE:m4", "RELEASE:r4"], affectedSprints: ["s24"], affectedMilestones: ["m4"], affectedReleases: ["r4"] }, authoritativeRecordsChanged: false };
      scenarios.splice(0, scenarios.length, result);
      return route.fulfill({ status: 201, json: result });
    }
    if (path === "/api/dependencies/summary") return route.fulfill({ json: { criticalDependencies: 1, atRiskDependencies: 0, blockedDependencies: 1, overdueDependencies: 0, unownedDependencies: 0, criticalPaths: 1, generatedAt: "2026-08-15T00:00:00Z", source: "persisted" } });
    if (path === "/api/dependencies/graph") return route.fulfill({ json: { nodes: [{ id: "SYSTEM:customer-api", entityType: "SYSTEM", entityId: "customer-api", name: "Customer API", upstreamCount: 1, downstreamCount: 1 }, { id: "WORK_ITEM:mobile", entityType: "WORK_ITEM", entityId: "mobile", name: "Mobile App", upstreamCount: 1, downstreamCount: 1 }, { id: "SPRINT:s24", entityType: "SPRINT", entityId: "s24", name: "Sprint 24", upstreamCount: 1, downstreamCount: 1 }, { id: "RELEASE:r4", entityType: "RELEASE", entityId: "r4", name: "Release 4", upstreamCount: 1, downstreamCount: 0 }], edges: [{ id: "dep-18", reference: "D-018", source: "SYSTEM:customer-api", target: "WORK_ITEM:mobile", relationshipType: "DEPENDS_ON", status: "BLOCKED", criticalPath: true }, { id: "dep-19", reference: "D-019", source: "WORK_ITEM:mobile", target: "SPRINT:s24", relationshipType: "DELIVERS_TO", status: "AT_RISK", criticalPath: true }, { id: "dep-20", reference: "D-020", source: "SPRINT:s24", target: "RELEASE:r4", relationshipType: "DELIVERS_TO", status: "IN_PROGRESS", criticalPath: true }], nodeCount: 4, edgeCount: 3, traceId: "trace-e2e", generatedAt: "2026-08-15T00:00:00Z" } });
    if (path === "/api/dependencies/critical-paths") return route.fulfill({ json: { items: [{ id: "CP-001", classification: "CALCULATED_CRITICAL_PATH", nodes: ["SYSTEM:customer-api", "WORK_ITEM:mobile", "SPRINT:s24", "RELEASE:r4"], pathLength: 3, currentDelayDays: 5, dataCompleteness: 1, limitations: [] }] } });
    if (path === "/api/dependencies/bottlenecks") return route.fulfill({ json: { items: [] } });
    if (path === "/api/dependencies/detected") return route.fulfill({ json: { items: [] } });
    if (path === "/api/dependencies/dep-18") return route.fulfill({ json: { item, upstream: [{ id: "SYSTEM:payment-api", depth: 1 }], downstream: [{ id: "SPRINT:s24", depth: 1 }, { id: "MILESTONE:m4", depth: 2 }, { id: "RELEASE:r4", depth: 3 }], evidence: [{ id: "ev-1", title: "Provider delivery status", summary: "Synthetic authorized status evidence.", sourceType: "STATUS_UPDATE", sourceSystem: "MANUAL", capturedAt: "2026-08-15T00:00:00Z" }], recommendations: [], recommendationDrafts: [], proposals, scenarios, history: [{ id: "history-1", eventType: "STATUS_TRANSITION", previousStatus: "AT_RISK", newStatus: "BLOCKED", note: "Provider forecast moved.", actorId: "owner-1", changedAt: "2026-08-14T00:00:00Z" }], relatedRAID: [], externalWrites: false } });
    if (path === "/api/dependencies") return route.fulfill({ json: { items: [item], page: 1, pageSize: 20, total: 1, pages: 1, generatedAt: "2026-08-15T00:00:00Z", source: "persisted" } });
    return route.fulfill({ status: 404, json: { detail: "Not mocked" } });
  });
  return { proposals, scenarios };
}

test("dependency graph, evidence, scenario and proposed intervention journey", async ({ page }) => {
  const state = await installDependencyApi(page);
  await page.goto("/dependencies");
  await expect(page).toHaveTitle("Dependency Intelligence | Axiom Delivery AI");
  await expect(page.getByRole("button", { name: /Critical dependencies/ })).toContainText("1");
  await page.getByRole("tab", { name: "Graph" }).click();
  await expect(page.getByRole("heading", { name: "Accessible relationship view" })).toBeVisible();
  await page.getByRole("button", { name: "Zoom in" }).click();
  await page.getByRole("button", { name: "Fit dependency graph to view" }).click();
  await page.getByRole("button", { name: "Select D-018" }).click();
  await page.getByRole("button", { name: "Expand upstream" }).click();
  await expect(page.getByRole("status")).toContainText("upstream node");
  await page.getByRole("button", { name: "Expand downstream" }).click();
  await expect(page.getByRole("status")).toContainText("downstream node");
  await page.getByRole("button", { name: "Highlight critical path" }).click();
  await expect(page.getByRole("status")).toContainText("critical path highlighted");
  await page.getByRole("button", { name: "D-018", exact: true }).click();
  const detail = page.getByRole("dialog", { name: "D-018" });
  await expect(detail).toContainText("owner-1");
  await expect(detail).toContainText("2026-08-18");
  await expect(detail).toContainText("Provider delivery status");
  await expect(detail.getByRole("link", { name: /Ask Axiom/ })).toHaveAttribute("href", "/copilot?dependency=dep-18");
  await detail.getByRole("button", { name: "Run 5-day impact" }).click();
  await detail.getByRole("button", { name: "Close dependency details" }).click();
  await expect(page.getByText(/authoritative records changed: false/)).toBeVisible();
  await expect(page.getByText(/Sprints: s24 · Releases: r4/)).toBeVisible();
  await page.goto("/dependencies/dep-18");
  await page.getByLabel("Draft escalation").fill("Escalate D-018 to the provider owner.");
  await page.getByRole("button", { name: "Save as proposed" }).click();
  await expect(page.getByText(/Nothing was executed externally/)).toBeVisible();
  await page.reload();
  await expect(page.getByRole("dialog", { name: "D-018" })).toContainText("Escalate D-018 to the provider owner.");
  await expect(page.getByRole("dialog", { name: "D-018" })).toContainText("STATUS TRANSITION");
  expect(state.proposals).toHaveLength(1);
  expect(state.scenarios).toHaveLength(1);
  const accessibility = await new AxeBuilder({ page }).disableRules(["color-contrast"]).analyze();
  expect(accessibility.violations.filter(result => ["critical", "serious"].includes(result.impact || ""))).toEqual([]);
});

test("cycle rejection is visible and leaves the reviewed form open", async ({ page }) => {
  await installDependencyApi(page);
  await page.goto("/dependencies");
  await page.getByRole("button", { name: "Add Dependency" }).click();
  await page.getByLabel("Reference").fill("D-CYCLE");
  await page.getByLabel("Title").fill("Rejected cycle");
  await page.getByLabel("Description").fill("Synthetic cycle candidate.");
  await page.getByLabel("Provider entity ID").fill("r4");
  await page.getByLabel("Consumer entity ID").fill("customer-api");
  await page.getByRole("button", { name: "Create reviewed dependency" }).click();
  await expect(page.getByRole("status")).toContainText("Cycle detected: RELEASE:r4 → SYSTEM:customer-api → RELEASE:r4");
  await expect(page.getByRole("heading", { name: "Add dependency" })).toBeVisible();
});

for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 768, height: 1024 }, { width: 390, height: 844 }]) {
  test(`dependency page remains usable at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await installDependencyApi(page);
    await page.goto("/dependencies");
    await expect(page.getByRole("heading", { name: "Dependency Intelligence" })).toBeVisible();
    await page.getByRole("tab", { name: "Register" }).click();
    await expect(page.getByRole("button", { name: "D-018" }).first()).toBeVisible();
  });
}
