import { describe, expect, it } from "vitest";
import { getMockRAIDDetail, getMockRAIDItems, mockRAIDItems, mockRAIDSummary } from "./mockRAID";

describe("RAID demo data", () => {
  it("covers every supported RAID type", () => {
    expect(new Set(mockRAIDItems.map((item) => item.itemType))).toEqual(new Set(["RISK", "ASSUMPTION", "ISSUE", "DEPENDENCY", "DECISION", "ACTION"]));
    expect(mockRAIDItems).toHaveLength(12);
  });

  it("supports register filters and URL-addressable details", () => {
    const risks = getMockRAIDItems({ type: "RISK", exposure_band: "CRITICAL" });
    expect(risks.items.map((item) => item.reference)).toEqual(["R-031"]);
    expect(getMockRAIDDetail("risk-payment-api")?.item.name).toBe("Payment API provider capacity");
    expect(getMockRAIDDetail("risk-payment-api")?.source).toBe("mock");
  });

  it("keeps executive summary counts aligned to the demo register", () => {
    expect(mockRAIDSummary).toMatchObject({ criticalRisks: 1, openIssues: 2, atRiskDependencies: 2, pendingDecisions: 2, overdueActions: 1, unvalidatedAssumptions: 2 });
  });
});
