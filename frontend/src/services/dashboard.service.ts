import api from "./api";

export const getDashboardMetrics = () =>
  api
    .get("/api/dashboard/metrics")
    .then(({ data }) => data);

export const getExecutionTrends = () =>
  api
    .get("/api/dashboard/executions/trends")
    .then(({ data }) => data);

export const getRecentExecutions = () =>
  api
    .get("/api/dashboard/recent-executions")
    .then(({ data }) => data);

export const getAgentStatus = () =>
  api
    .get("/api/dashboard/agents/status")
    .then(({ data }) => data);

export const getWorkflowDistribution = () =>
  api
    .get("/api/dashboard/workflow-distribution")
    .then(({ data }) => data);