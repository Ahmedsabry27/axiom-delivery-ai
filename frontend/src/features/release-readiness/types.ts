export type CriterionStatus =
  | "PASSED"
  | "FAILED"
  | "PENDING"
  | "MISSING EVIDENCE"
  | "WAIVED"
  | "CONDITIONAL";

export type Recommendation = "GO" | "CONDITIONAL GO" | "NO-GO" | "INSUFFICIENT EVIDENCE";
export type Severity = "Critical" | "High" | "Medium" | "Low";
export type HardeningStatus = "PASS" | "FAIL" | "PENDING";

export interface ReadinessCriterion {
  id: string;
  name: string;
  status: CriterionStatus;
  mandatory: boolean;
  owner: string;
  lastUpdated: string;
  evidenceLabel?: string;
  evidenceLink?: string;
  dueDate?: string;
  note: string;
  blocking?: boolean;
}

export interface ReleaseBlocker {
  id: string;
  title: string;
  severity: Severity;
  owner: string;
  due: string;
  linkedCriterion: string;
  status: string;
  evidenceLink: string;
}

export interface ReleaseCondition {
  id: string;
  type: "condition" | "exception";
  summary: string;
  owner: string;
  due: string;
  approvedBy?: string;
  validUntil?: string;
}

export interface EvidenceItem {
  id: string;
  title: string;
  type: string;
  source: string;
  owner: string;
  recorded: string;
  status: "Verified" | "Pending" | "Missing";
}

export interface ReleaseDecisionHistoryEntry {
  id: string;
  decision: "GO" | "CONDITIONAL GO" | "NO-GO" | "Decision deferred";
  owner: string;
  role: string;
  timestamp: string;
  rationale: string;
  conditions?: string[];
}

export interface ReleaseRecommendation {
  level: Recommendation;
  summary: string;
  conditions: string[];
  evidenceConfidence: "High" | "Medium" | "Low";
  evidenceCoverage: number;
  evidenceVerified: number;
  evidenceTotal: number;
  evaluatedAt: string;
}

export interface TraceSpan {
  id: string;
  stage: string;
  status: HardeningStatus;
  durationMs: number;
  timestamp: string;
  identifier: string;
  metadata?: string;
}

export interface ModelMetricRow {
  model: string;
  requests: number;
  inputTokens: number;
  outputTokens: number;
  avgLatencyMs: number;
  successRate: number;
  failures: number;
  retries: number;
  estimatedCost: number;
}

export interface AIQualityMetric {
  label: string;
  value: number;
  threshold: number;
}

export interface SecurityControl {
  name: string;
  status: HardeningStatus;
  summary: string;
}

export interface RegressionJourneyStep {
  label: string;
  status: "done" | "pending";
}

export interface ReleaseRecord {
  id: string;
  name: string;
  environment: string;
  targetDate: string;
  releaseOwner: string;
  decisionOwner: string;
  status: Recommendation | "PENDING";
  currentDecision: ReleaseDecisionHistoryEntry | null;
  criteria: ReadinessCriterion[];
  blockers: ReleaseBlocker[];
  conditions: ReleaseCondition[];
  exceptions: ReleaseCondition[];
  evidence: EvidenceItem[];
  recommendation: ReleaseRecommendation;
  decisionHistory: ReleaseDecisionHistoryEntry[];
  hardening: {
    trace: {
      id: string;
      totalLatencyMs: number;
      spans: TraceSpan[];
    };
    authorization: {
      testsExecuted: number;
      passed: number;
      failed: number;
      lastValidation: string;
      controls: { label: string; status: HardeningStatus }[];
    };
    monitoring: {
      requests: number;
      successRate: number;
      averageLatencyMs: number;
      tokens: number;
      estimatedCost: number;
      retries: number;
      modelMetrics: ModelMetricRow[];
    };
    quality: {
      metrics: AIQualityMetric[];
      overallStatus: HardeningStatus;
      thresholdMet: string;
    };
    security: {
      controls: SecurityControl[];
      findings: { level: "Medium" | "Low"; count: number }[];
      overallStatus: HardeningStatus;
    };
    regression: {
      story: string;
      steps: RegressionJourneyStep[];
      execution: string;
      duration: string;
      environment: string;
      status: HardeningStatus;
    };
  };
}
