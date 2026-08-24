import type { CriterionStatus, ReadinessCriterion, Recommendation } from "../types";

const WEIGHTS: Record<CriterionStatus, number> = {
  PASSED: 1,
  FAILED: 0,
  PENDING: 0,
  "MISSING EVIDENCE": 0,
  WAIVED: 1,
  CONDITIONAL: 0.6,
};

export function calculateReadiness(criteria: ReadinessCriterion[]) {
  const total = criteria.length;
  const passed = criteria.filter((criterion) => criterion.status === "PASSED" || criterion.status === "WAIVED").length;
  const blocked = criteria.filter((criterion) => criterion.blocking && (criterion.status === "PENDING" || criterion.status === "FAILED" || criterion.status === "MISSING EVIDENCE" || criterion.status === "CONDITIONAL")).length;
  const missingEvidence = criteria.filter((criterion) => criterion.status === "MISSING EVIDENCE").length;
  const conditionCount = criteria.filter((criterion) => criterion.status === "CONDITIONAL").length;
  const weighted = criteria.reduce((sum, criterion) => sum + WEIGHTS[criterion.status], 0);
  const percentage = Math.round((weighted / total) * 100);

  return {
    total,
    passed,
    blocked,
    missingEvidence,
    conditionCount,
    weighted,
    percentage,
  };
}

export function getRecommendation(criteria: ReadinessCriterion[], score: number): { level: Recommendation; summary: string } {
  const failedBlocking = criteria.some((criterion) => criterion.blocking && criterion.status === "FAILED");
  const unresolvedBlocking = criteria.some((criterion) => criterion.blocking && (criterion.status === "PENDING" || criterion.status === "MISSING EVIDENCE"));
  const conditional = criteria.some((criterion) => criterion.status === "CONDITIONAL");

  if (failedBlocking) {
    return {
      level: "NO-GO",
      summary: "A blocking criterion has failed and the release is not ready for production deployment.",
    };
  }

  if (unresolvedBlocking || conditional) {
    return {
      level: "CONDITIONAL GO",
      summary: "The release can proceed only if the documented blocking condition is satisfied before deployment.",
    };
  }

  if (score >= 85) {
    return {
      level: "GO",
      summary: "The release is ready for production with the current evidence package.",
    };
  }

  return {
    level: "INSUFFICIENT EVIDENCE",
    summary: "The evidence package is incomplete and additional validation is required before a decision.",
  };
}
