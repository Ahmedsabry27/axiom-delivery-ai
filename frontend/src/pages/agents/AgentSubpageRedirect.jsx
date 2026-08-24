import { Navigate, useParams } from "react-router-dom";

const supportedTabs = new Set([
  "overview",
  "configuration",
  "capabilities",
  "knowledge",
  "models",
  "evaluations",
  "executions",
  "versions",
  "access",
  "test",
]);

const existingTab = {
  configuration: "instructions",
  capabilities: "tools",
  models: "model",
  evaluations: "analytics",
  test: "test-console",
};

export default function AgentSubpageRedirect() {
  const { agentId, tab } = useParams();
  const destination = supportedTabs.has(tab) ? existingTab[tab] ?? tab : "overview";
  return <Navigate replace to={`/agents/${agentId}?tab=${destination}`} />;
}
