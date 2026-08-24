import api from "./api";
import type { DeliveryCommandCenterData, MetricSummary, MyDayData } from "../types/delivery";

type CommandCenterInput = Omit<
  Partial<DeliveryCommandCenterData>,
  "portfolioHealth" | "sprintPredictability" | "openRisks" | "dependencies"
> & {
  portfolioHealth?: Partial<MetricSummary>;
  sprintPredictability?: Partial<MetricSummary>;
  openRisks?: Partial<MetricSummary>;
  dependencies?: Partial<MetricSummary>;
};

const metricDefaults = (label: string) => ({
  label,
  value: 0,
  status: "UNKNOWN",
  detail: "No persisted data available",
  change: 0,
  changeLabel: "insufficient history",
  state: "missing" as const,
});

export function normalizeCommandCenterData(
  value: CommandCenterInput | null | undefined,
): DeliveryCommandCenterData {
  const data = value ?? {};
  return {
    generatedAt: data.generatedAt || new Date().toISOString(),
    portfolioHealth: { ...metricDefaults("Portfolio Health"), ...(data.portfolioHealth ?? {}) },
    sprintPredictability: { ...metricDefaults("Sprint Predictability"), ...(data.sprintPredictability ?? {}) },
    openRisks: { ...metricDefaults("Open Risks"), ...(data.openRisks ?? {}) },
    dependencies: { ...metricDefaults("Dependencies"), ...(data.dependencies ?? {}) },
    deliveryTrend: Array.isArray(data.deliveryTrend) ? data.deliveryTrend : [],
    attentionItems: Array.isArray(data.attentionItems) ? data.attentionItems : [],
    recommendations: Array.isArray(data.recommendations) ? data.recommendations : [],
    contexts: Array.isArray(data.contexts) ? data.contexts : [],
  };
}

export function normalizeMyDayData(
  value: Partial<MyDayData> | null | undefined,
): MyDayData {
  const data = value ?? {};
  return {
    generatedAt: data.generatedAt || new Date().toISOString(),
    focusScore: typeof data.focusScore === "number" ? data.focusScore : 0,
    items: Array.isArray(data.items) ? data.items : [],
    briefings: Array.isArray(data.briefings) ? data.briefings : [],
  };
}

export interface DeliveryRepository {
  getCommandCenter(signal?: AbortSignal, contextId?: string): Promise<DeliveryCommandCenterData>;
  getMyDay(signal?: AbortSignal): Promise<MyDayData>;
}

export class MockDeliveryRepository implements DeliveryRepository {
  constructor(private readonly data: DeliveryCommandCenterData, private readonly myDay?: MyDayData) {}
  async getCommandCenter(signal?: AbortSignal, contextId?: string): Promise<DeliveryCommandCenterData> {
    void contextId;
    if (signal?.aborted) throw new DOMException("Request aborted", "AbortError");
    return normalizeCommandCenterData({ ...this.data, generatedAt: new Date().toISOString() });
  }
  async getMyDay(signal?: AbortSignal): Promise<MyDayData> {
    if (signal?.aborted) throw new DOMException("Request aborted", "AbortError");
    if (!this.myDay) throw new Error("Mock My Day data is required");
    return normalizeMyDayData({ ...this.myDay, generatedAt: new Date().toISOString() });
  }
}

export class ApiDeliveryRepository implements DeliveryRepository {
  async getCommandCenter(signal?: AbortSignal, contextId?: string): Promise<DeliveryCommandCenterData> {
    const { data } = await api.get<DeliveryCommandCenterData>("/api/delivery/command-center", {
      signal,
      params: contextId && contextId !== "portfolio-all" ? { context_id: contextId } : undefined,
    });
    return normalizeCommandCenterData(data);
  }
  async getMyDay(signal?: AbortSignal): Promise<MyDayData> {
    const { data } = await api.get<MyDayData>("/api/delivery/my-day", { signal });
    return normalizeMyDayData(data);
  }
}

export const createDeliveryRepository = (useMock: boolean, mockData?: DeliveryCommandCenterData, myDay?: MyDayData): DeliveryRepository => {
  if (useMock) {
    if (!mockData) throw new Error("Mock delivery data is required when mock mode is enabled");
    return new MockDeliveryRepository(mockData, myDay);
  }
  return new ApiDeliveryRepository();
};
