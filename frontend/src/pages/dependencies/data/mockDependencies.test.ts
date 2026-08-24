import { describe, expect, it } from "vitest";
import { getMockDependencies, getMockDependencyDetail, getMockDependencyScenario, mockDependencyGraph, mockDependencyItems, mockDependencySummary } from "./mockDependencies";

describe("Dependencies demo data", () => {
  it("provides an operational dependency portfolio and graph", () => {
    expect(mockDependencyItems).toHaveLength(8);
    expect(mockDependencyGraph.edgeCount).toBe(8);
    expect(mockDependencyGraph.nodes.length).toBeGreaterThan(8);
    expect(mockDependencySummary).toMatchObject({ criticalDependencies: 2, blockedDependencies: 1, criticalPaths: 2 });
  });

  it("supports register filtering and URL-addressable details", () => {
    expect(getMockDependencies({ status: "BLOCKED" }).items.map((item) => item.reference)).toEqual(["D-018"]);
    expect(getMockDependencies({ unowned: true }).items.map((item) => item.reference)).toEqual(["D-038"]);
    expect(getMockDependencyDetail("dep-payment-api")?.item.name).toBe("Payment API delivery");
  });

  it("returns a read-only impact scenario", () => {
    const scenario = getMockDependencyScenario("dep-payment-api", 5);
    expect(scenario.changeValue.days).toBe(5);
    expect(scenario.scenarioResult.affectedReleases).toContain("rel-001");
    expect(scenario.authoritativeRecordsChanged).toBe(false);
  });
});
