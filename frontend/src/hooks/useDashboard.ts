import { useQueries } from "@tanstack/react-query";
import type { QueryFunction, QueryKey } from "@tanstack/react-query";
import {
  getAgentStatus,
  getDashboardMetrics,
  getExecutionTrends,
  getRecentExecutions,
  getWorkflowDistribution,
} from "../services/dashboard.service";

const options = (queryKey: QueryKey, queryFn: QueryFunction) => ({ queryKey, queryFn, staleTime: 20_000, refetchInterval: 30_000 });

export function useDashboard() {
  const [metrics, trends, recent, agents, distribution] = useQueries({ queries: [
    options(["dashboard", "metrics"], getDashboardMetrics),
    options(["dashboard", "trends"], getExecutionTrends),
    options(["dashboard", "recent"], getRecentExecutions),
    options(["dashboard", "agents"], getAgentStatus),
    options(["dashboard", "distribution"], getWorkflowDistribution),
  ] });
  return {
    metrics: metrics.data,
    trends: trends.data,
    recent: recent.data,
    agents: agents.data,
    distribution: distribution.data,
    isLoading: [metrics, trends, recent, agents, distribution].some((query) => query.isLoading),
    error: [metrics, trends, recent, agents, distribution].find((query) => query.error)?.error,
    refetch: () => Promise.all([metrics.refetch(), trends.refetch(), recent.refetch(), agents.refetch(), distribution.refetch()]),
  };
}
