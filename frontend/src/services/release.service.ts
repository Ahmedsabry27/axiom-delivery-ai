import { isDeliveryMockMode } from "../config/deliveryDataMode";
import type { Release, ReleaseDecision, ReleaseLifecycleStatus, ReleaseRecommendation } from "../features/releases/types";
import api from "./api";

type ApiRelease = Partial<Release> & {
  releaseId?: string;
  recordVersion?: number;
};

const emptyHardening: Release["hardening"] = {
  trace: { id: "Not available", totalLatencyMs: 0, spans: [] },
  authorization: { testsExecuted: 0, passed: 0, failed: 0, controls: [], lastValidation: "" },
  monitoring: { requests: 0, successRate: 0, averageLatencyMs: 0, tokens: 0, estimatedCost: 0, retries: 0, modelMetrics: [] },
  quality: { metrics: [], overallStatus: "PENDING", thresholdMet: "Validation data is pending" },
  security: { controls: [], findings: [], overallStatus: "PENDING" },
  regression: { story: "", steps: [], execution: "", duration: "Not available", environment: "Not available", status: "PENDING" },
};

function normalizeLifecycle(value: unknown): ReleaseLifecycleStatus {
  const lifecycle = String(value ?? "").trim().toUpperCase().replaceAll("_", " ");
  const aliases: Record<string, ReleaseLifecycleStatus> = {
    RELEASED: "DEPLOYED",
    READY: "READY FOR DECISION",
    "AT RISK": "VALIDATION",
    PLANNED: "PLANNING",
  };
  const valid: ReleaseLifecycleStatus[] = ["PLANNING", "IN PROGRESS", "VALIDATION", "READY FOR DECISION", "APPROVED", "SCHEDULED", "DEPLOYING", "DEPLOYED", "BLOCKED", "CANCELLED"];
  return aliases[lifecycle] ?? (valid.includes(lifecycle as ReleaseLifecycleStatus) ? lifecycle as ReleaseLifecycleStatus : "PLANNING");
}

function normalizeRecommendation(value: unknown, score: number): ReleaseRecommendation {
  const recommendation = String(value ?? "").trim().toUpperCase().replaceAll("_", " ");
  const valid: ReleaseRecommendation[] = ["GO", "CONDITIONAL GO", "NO-GO", "INSUFFICIENT EVIDENCE"];
  if (valid.includes(recommendation as ReleaseRecommendation)) return recommendation as ReleaseRecommendation;
  if (score >= 85) return "GO";
  if (score >= 60) return "CONDITIONAL GO";
  return score > 0 ? "NO-GO" : "INSUFFICIENT EVIDENCE";
}

export function normalizeRelease(input: ApiRelease): Release {
  const score = Number.isFinite(Number(input.readinessScore)) ? Number(input.readinessScore) : 0;
  const id = String(input.id ?? input.releaseId ?? "unknown-release");
  const targetDate = input.targetDate || new Date().toISOString();
  const updatedAt = input.updatedAt || targetDate;
  const evidence = Array.isArray(input.evidence) ? input.evidence : [];
  const verified = evidence.filter((item) => item.status === "VERIFIED").length;
  const missing = evidence.filter((item) => item.status === "MISSING").length;

  return {
    ...input,
    id,
    releaseId: String(input.releaseId ?? id),
    name: String(input.name ?? "Untitled release"),
    version: String(input.version ?? input.recordVersion ?? "—"),
    releaseType: input.releaseType ?? "Minor Release",
    environment: input.environment ?? "PROD",
    targetDate,
    releaseOwner: String(input.releaseOwner ?? "Unassigned"),
    businessOwner: String(input.businessOwner ?? "Unassigned"),
    technicalOwner: String(input.technicalOwner ?? "Unassigned"),
    lifecycle: normalizeLifecycle(input.lifecycle),
    readinessScore: score,
    recommendation: normalizeRecommendation(input.recommendation, score),
    decisionOwner: String(input.decisionOwner ?? "Unassigned"),
    decisionHistory: Array.isArray(input.decisionHistory) ? input.decisionHistory : [],
    currentDecision: input.currentDecision ?? null,
    criteria: Array.isArray(input.criteria) ? input.criteria : [],
    blockers: Array.isArray(input.blockers) ? input.blockers : [],
    risks: Array.isArray(input.risks) ? input.risks : [],
    conditions: Array.isArray(input.conditions) ? input.conditions : [],
    exceptions: Array.isArray(input.exceptions) ? input.exceptions : [],
    evidence,
    hardening: {
      ...emptyHardening,
      ...(input.hardening ?? {}),
      trace: { ...emptyHardening.trace, ...(input.hardening?.trace ?? {}), spans: input.hardening?.trace?.spans ?? [] },
      authorization: { ...emptyHardening.authorization, ...(input.hardening?.authorization ?? {}), controls: input.hardening?.authorization?.controls ?? [] },
      monitoring: { ...emptyHardening.monitoring, ...(input.hardening?.monitoring ?? {}), modelMetrics: input.hardening?.monitoring?.modelMetrics ?? [] },
      quality: { ...emptyHardening.quality, ...(input.hardening?.quality ?? {}), metrics: input.hardening?.quality?.metrics ?? [] },
      security: { ...emptyHardening.security, ...(input.hardening?.security ?? {}), controls: input.hardening?.security?.controls ?? [], findings: input.hardening?.security?.findings ?? [] },
      regression: { ...emptyHardening.regression, ...(input.hardening?.regression ?? {}), steps: input.hardening?.regression?.steps ?? [] },
    },
    phase: String(input.phase ?? normalizeLifecycle(input.lifecycle)),
    changeReference: String(input.changeReference ?? "Not assigned"),
    statusLabel: String(input.statusLabel ?? normalizeLifecycle(input.lifecycle)),
    updatedAt,
    evidenceSummary: input.evidenceSummary ?? { total: evidence.length, verified, missing, expired: 0 },
  };
}

async function developmentReleases(): Promise<Release[]> {
  if (!import.meta.env.DEV) throw new Error("Mock release data is unavailable in this build");
  const [{ mockReleases }, { mockReleaseNotesMap }] = await Promise.all([
    import("../features/releases/data/mockReleases"),
    import("../features/releases/data/mockReleaseNotes"),
  ]);
  return mockReleases.map((release) => ({
    ...release,
    releaseNotes: release.releaseNotes ?? mockReleaseNotesMap[release.id],
  }));
}

export async function getReleases(signal?: AbortSignal): Promise<Release[]> {
  if (isDeliveryMockMode()) return developmentReleases();
  const response = await api.get<{ items?: ApiRelease[] }>("/api/releases", { signal });
  return Array.isArray(response.data.items) ? response.data.items.map(normalizeRelease) : [];
}

export async function getRelease(id: string, signal?: AbortSignal): Promise<Release> {
  if (isDeliveryMockMode()) {
    const release = (await developmentReleases()).find((item) => item.id === id);
    if (!release) throw new Error("Release not found");
    return release;
  }
  return normalizeRelease((await api.get<ApiRelease>(`/api/releases/${id}`, { signal })).data);
}

export async function recordReleaseDecision(
  releaseId: string,
  decision: Pick<ReleaseDecision, "decision" | "rationale" | "conditions" | "role">,
): Promise<Release> {
  return normalizeRelease((await api.post<ApiRelease>(`/api/releases/${releaseId}/decisions`, decision)).data);
}
