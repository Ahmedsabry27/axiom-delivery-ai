export type ReleaseEnvironment = "PROD" | "UAT" | "STAGING" | "DEV";
export type ReleaseLifecycleStatus =
  | "PLANNING"
  | "IN PROGRESS"
  | "VALIDATION"
  | "READY FOR DECISION"
  | "APPROVED"
  | "SCHEDULED"
  | "DEPLOYING"
  | "DEPLOYED"
  | "BLOCKED"
  | "CANCELLED";

export type ReleaseRecommendation = "GO" | "CONDITIONAL GO" | "NO-GO" | "INSUFFICIENT EVIDENCE";
export type ReleaseReadinessStatus = "PASSED" | "FAILED" | "PENDING" | "MISSING EVIDENCE" | "WAIVED" | "CONDITIONAL";
export type ReleaseRiskLevel = "Critical" | "High" | "Medium" | "Low";
export type ReleaseRiskStatus = "Open" | "Mitigated";

export interface ReadinessCriterion {
  id: string;
  name: string;
  status: ReleaseReadinessStatus;
  mandatory: boolean;
  owner: string;
  lastUpdated: string;
  note: string;
  evidenceLabel?: string;
  blocking?: boolean;
}

export interface EvidenceItem {
  id: string;
  title: string;
  category: string;
  linkedCriterion: string;
  source: string;
  owner: string;
  status: "VERIFIED" | "PENDING" | "MISSING";
  recorded: string;
}

export interface ReleaseBlocker {
  id: string;
  title: string;
  severity: ReleaseRiskLevel;
  owner: string;
  due: string;
  linkedCriterion: string;
  status: "Open" | "Mitigated";
}

export interface ReleaseRisk {
  id: string;
  title: string;
  likelihood: "High" | "Medium" | "Low";
  impact: "High" | "Medium" | "Low";
  severity: ReleaseRiskLevel;
  owner: string;
  mitigation: string;
  status: ReleaseRiskStatus;
}

export interface ReleaseCondition {
  id: string;
  summary: string;
  owner: string;
  due: string;
  type: "condition" | "exception";
  approvedBy?: string;
  validUntil?: string;
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

export interface ReleaseDecision {
  decision: "GO" | "CONDITIONAL GO" | "NO-GO" | "Decision deferred";
  owner: string;
  role: string;
  timestamp: string;
  rationale: string;
  conditions: string[];
}

export interface TraceSpan {
  id: string;
  stage: string;
  status: "PASS" | "FAIL" | "PENDING";
  durationMs: number;
  timestamp: string;
  identifier: string;
}

export interface ReleaseHardening {
  trace: {
    id: string;
    totalLatencyMs: number;
    spans: TraceSpan[];
  };
  authorization: {
    testsExecuted: number;
    passed: number;
    failed: number;
    controls: Array<{ label: string; status: "PASS" | "FAIL" | "PENDING" }>;
    lastValidation: string;
  };
  monitoring: {
    requests: number;
    successRate: number;
    averageLatencyMs: number;
    tokens: number;
    estimatedCost: number;
    retries: number;
    modelMetrics: Array<{
      model: string;
      requests: number;
      inputTokens: number;
      outputTokens: number;
      avgLatencyMs: number;
      successRate: number;
      failures: number;
      retries: number;
      estimatedCost: number;
    }>;
  };
  quality: {
    metrics: Array<{ label: string; value: number; threshold: number }>;
    overallStatus: "PASS" | "FAIL" | "PENDING";
    thresholdMet: string;
  };
  security: {
    controls: Array<{ name: string; status: "PASS" | "FAIL" | "PENDING"; summary: string }>;
    findings: Array<{ level: "Medium" | "Low"; count: number }>;
    overallStatus: "PASS" | "FAIL" | "PENDING";
  };
  regression: {
    story: string;
    steps: Array<{ label: string; status: "done" | "pending" }>;
    execution: string;
    duration: string;
    environment: string;
    status: "PASS" | "FAIL" | "PENDING";
  };
}

export type ReleaseNoteCategory =
  | "FEATURE"
  | "ENHANCEMENT"
  | "BUG_FIX"
  | "TECHNICAL"
  | "SECURITY"
  | "PERFORMANCE"
  | "KNOWN_ISSUE"
  | "DEPRECATED";

export interface JiraReference {
  key: string;
  type?: string;
  url?: string;
  epicKey?: string;
}

export interface ReleaseNoteItem {
  id: string;
  jira: JiraReference;
  category: ReleaseNoteCategory;
  title: string;
  description: string;
  component: string;
  owner?: string;
  status: "DONE" | "FIXED" | "VERIFIED" | "KNOWN_ISSUE" | "DEFERRED" | "REMOVED";
  severity?: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  businessImpact?: string;
  resolution?: string;
  validationStatus?: string;
  relatedCriterionId?: string;
  relatedEvidenceIds?: string[];
  relatedBlockerId?: string;
  workaround?: string;
  targetFix?: string;
}

export interface ReleaseValidationTest {
  label: string;
  status: "PASS" | "FAIL" | "PENDING";
  count?: string;
  detail?: string;
}

export interface ReleaseNotes {
  id: string;
  releaseId: string;
  summary: string;
  items: ReleaseNoteItem[];
  deploymentNotes?: {
    window?: string;
    strategy?: string;
    expectedDowntime?: string;
    requiresDatabaseMigration?: boolean;
    migrationHeadHash?: string;
    featureFlags?: string[];
    requiresPostDeploymentValidation?: boolean;
  };
  configurationChanges?: {
    newEnvironmentVariables?: string[];
    featureFlags?: string[];
    infrastructureChanges?: string;
    databaseChanges?: string;
  };
  dependencies?: Array<{ name: string; status: string }>;
  impactedComponents?: string[];
  impactedPersonas?: string[];
  validationSummary?: ReleaseValidationTest[];
  jiraTraceability?: {
    totalItems: number;
    linkedItems: number;
    epicCoverage?: Array<{ epicKey: string; epicTitle: string; itemCount: number }>;
  };
}

export interface Release {
  id: string;
  name: string;
  version: string;
  releaseType: "Major Release" | "Minor Release" | "Maintenance Release";
  environment: ReleaseEnvironment;
  targetDate: string;
  releaseOwner: string;
  businessOwner: string;
  technicalOwner: string;
  lifecycle: ReleaseLifecycleStatus;
  readinessScore: number;
  recommendation: ReleaseRecommendation;
  decisionOwner: string;
  decisionHistory: ReleaseDecisionHistoryEntry[];
  currentDecision: ReleaseDecision | null;
  criteria: ReadinessCriterion[];
  blockers: ReleaseBlocker[];
  risks: ReleaseRisk[];
  conditions: ReleaseCondition[];
  exceptions: ReleaseCondition[];
  evidence: EvidenceItem[];
  hardening: ReleaseHardening;
  releaseNotes?: ReleaseNotes;
  releaseId: string;
  phase: string;
  changeReference: string;
  statusLabel: string;
  updatedAt: string;
  evidenceSummary: {
    total: number;
    verified: number;
    missing: number;
    expired: number;
  };
  recordVersion?: number;
}
