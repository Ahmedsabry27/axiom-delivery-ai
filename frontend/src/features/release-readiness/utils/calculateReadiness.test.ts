import { describe, expect, it } from "vitest";
import { mockReleaseReadinessData } from "../data/mockReleaseReadiness";
import { calculateReadiness, getRecommendation } from "./calculateReadiness";

describe("release readiness calculation", () => {
  it("keeps the default governance scenario deterministic", () => {
    const release = mockReleaseReadinessData[0];
    const result = calculateReadiness(release.criteria);

    expect(result).toMatchObject({ percentage: 87, passed: 9, total: 11, blocked: 1 });
    expect(getRecommendation(release.criteria, result.percentage).level).toBe("CONDITIONAL GO");
  });

  it("treats an approved waiver as full weight and a condition as partial weight", () => {
    const result = calculateReadiness([
      { id: "waiver", name: "Waiver", status: "WAIVED", mandatory: true, owner: "Board", lastUpdated: "2026-10-04", note: "Approved" },
      { id: "condition", name: "Condition", status: "CONDITIONAL", mandatory: true, owner: "SRE", lastUpdated: "2026-10-04", note: "Verify" },
    ]);

    expect(result.weighted).toBe(1.6);
    expect(result.percentage).toBe(80);
  });
});
