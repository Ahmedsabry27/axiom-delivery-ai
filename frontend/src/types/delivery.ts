export interface MetricSummary {
  label: string;
  value: number;
  unit?: "%";
  status: string;
  detail: string;
  change: number;
  changeLabel: string;
  definition?: string;
  route?: string;
  state?: "ready" | "partial" | "missing";
}

export interface DeliveryTrendPoint {
  period: string;
  portfolioHealth: number;
  sprintPredictability: number;
  commitmentAchievement: number;
}

export interface AttentionItem {
  id: string;
  item: string;
  type: "Risk" | "Action" | "Dependency";
  impact: "High" | "Medium" | "Low";
  status: string;
  owner: string;
  dueDate: string;
  description: string;
  score?: number;
  scoreBreakdown?: string[];
  evidence?: EvidenceReference[];
  route?: string;
}

export interface AIRecommendation {
  id: string;
  title: string;
  priority: "Critical" | "High" | "Medium";
  explanation: string;
  affectedArea: string;
  evidenceCount: number;
  confidence: number;
  status?: "New" | "Reviewed" | "Dismissed" | "Proposed";
  evidence?: EvidenceReference[];
}

export interface DeliveryCommandCenterData {
  generatedAt: string;
  portfolioHealth: MetricSummary;
  sprintPredictability: MetricSummary;
  openRisks: MetricSummary;
  dependencies: MetricSummary;
  deliveryTrend: DeliveryTrendPoint[];
  attentionItems: AttentionItem[];
  recommendations: AIRecommendation[];
  contexts?: DeliveryContext[];
}

export interface DeliveryContext { id: string; name: string; type: "Portfolio" | "Programme" | "Project"; }
export interface MyDayItem { id: string; title: string; kind: "Attention" | "Meeting" | "Approval" | "Action" | "Dependency Candidate"; time?: string; dueDate?: string; priority: "Critical" | "High" | "Medium" | "Low"; context: string; summary: string; route?: string; }
export interface MyDayData { generatedAt: string; focusScore: number; items: MyDayItem[]; briefings: Array<{id:string; title:string; summary:string; evidenceCount:number}>; }

export type DeliveryHealth = "GREEN" | "AMBER" | "RED" | "UNKNOWN";
export type DeliveryStatus = "PLANNED" | "ACTIVE" | "AT_RISK" | "BLOCKED" | "COMPLETED" | "CANCELLED" | "ON_HOLD";
export type RAIDType = "RISK" | "ASSUMPTION" | "ISSUE" | "DEPENDENCY" | "DECISION" | "ACTION";
export type SourceSystem = "MANUAL" | "JIRA" | "AZURE_DEVOPS" | "SERVICENOW" | "SHAREPOINT" | "TEAMS" | "IMPORT";

export interface PersonSummary { id: string; displayName: string; email?: string; }
export interface DeliverySummaryBase { id: string; tenantId: string; name: string; status: DeliveryStatus; health?: DeliveryHealth; owner?: PersonSummary; externalId?: string; sourceSystem: SourceSystem; }
export interface PortfolioSummary extends DeliverySummaryBase { programmeCount: number; }
export interface ProgrammeSummary extends DeliverySummaryBase { portfolioId: string; projectCount: number; }
export interface ProjectSummary extends DeliverySummaryBase { programmeId: string; }
export interface TeamSummary extends DeliverySummaryBase { projectId: string; active: boolean; capacity?: number; }
export interface SprintSummary extends DeliverySummaryBase { projectId: string; teamId: string; startDate: string; endDate: string; committedPoints?: number; completedPoints?: number; }
export interface ReleaseSummary extends DeliverySummaryBase { projectId: string; plannedDate?: string; readinessScore?: number; }
export interface RAIDItemSummary { id: string; tenantId: string; projectId: string; itemType: RAIDType; title: string; status: DeliveryStatus; impact?: string; owner?: PersonSummary; dueDate?: string; }
export interface DependencySummary extends RAIDItemSummary { itemType: "DEPENDENCY"; upstreamRef: string; downstreamRef: string; criticalPath: boolean; }
export interface ActionSummary extends RAIDItemSummary { itemType: "ACTION"; completionStatus: string; }
export interface EvidenceReference { id: string; tenantId: string; sourceType: string; sourceSystem: SourceSystem; sourceRecordId: string; title: string; summary?: string; sourceUrl?: string; capturedAt?: string; contentHash?: string; }
