import { describe, expect, it } from "vitest";
import { mockReleases } from "../data/mockReleases";
import { calculateReleaseReadiness, calculateReleaseRecommendation } from "./calculateReleaseReadiness";

describe("calculateReleaseReadiness", () => {
  it("calculates the default demo score from criteria", () => {
    const release = mockReleases[0];
    expect(calculateReleaseReadiness(release.criteria)).toMatchObject({ percentage: 87, passed: 9, total: 11, blocked: 1 });
  });

  it("lets a failed mandatory blocker override a high score", () => {
    const criteria = mockReleases[0].criteria.map((criterion) => criterion.name === "Security Approval" ? { ...criterion, status: "FAILED" as const } : { ...criterion, status: "PASSED" as const });
    expect(calculateReleaseRecommendation(criteria, 96)).toBe("NO-GO");
  });
});
