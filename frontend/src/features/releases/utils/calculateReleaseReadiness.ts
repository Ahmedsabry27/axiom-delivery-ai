import type { ReadinessCriterion, ReleaseRecommendation } from "../types";

const STATUS_WEIGHT: Record<ReadinessCriterion["status"], number> = {
  PASSED: 1,
  WAIVED: 1,
  CONDITIONAL: 0.6,
  PENDING: 0,
  FAILED: 0,
  "MISSING EVIDENCE": 0,
};

export function calculateReleaseReadiness(criteria: ReadinessCriterion[]) {
  const total = criteria.length;
  let passed = 0;
  let missingEvidence = 0;
  let blocked = 0;
  let conditional = 0;

  for (const criterion of criteria) {
    if (criterion.status === "PASSED" || criterion.status === "WAIVED") {
      passed += 1;
      continue;
    }

    if (criterion.status === "CONDITIONAL") {
      conditional += 1;
      continue;
    }

    if (criterion.status === "MISSING EVIDENCE") {
      missingEvidence += 1;
    }

    if (criterion.status === "PENDING" || criterion.status === "FAILED") {
      missingEvidence += 1;
    }

    if (criterion.blocking && (criterion.status === "PENDING" || criterion.status === "FAILED" || criterion.status === "MISSING EVIDENCE")) {
      blocked += 1;
    }
  }

  const weightedScore = Math.round((criteria.reduce((sum, criterion) => sum + STATUS_WEIGHT[criterion.status], 0) / Math.max(total, 1)) * 100);

  return {
    total,
    passed,
    conditional,
    missingEvidence,
    blocked,
    percentage: weightedScore,
  };
}

export function calculateReleaseRecommendation(criteria: ReadinessCriterion[], evidenceCoverage: number): ReleaseRecommendation {
  if (criteria.some((criterion) => criterion.blocking && criterion.status === "FAILED")) return "NO-GO";
  if (evidenceCoverage < 50) return "INSUFFICIENT EVIDENCE";
  if (criteria.some((criterion) => criterion.status === "CONDITIONAL" || (criterion.blocking && (criterion.status === "PENDING" || criterion.status === "MISSING EVIDENCE")))) return "CONDITIONAL GO";
  return "GO";
}
