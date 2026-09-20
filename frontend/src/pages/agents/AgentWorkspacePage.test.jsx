import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AgentWorkspacePage from "./AgentWorkspacePage";

const mocks = vi.hoisted(() => ({
  getAgent: vi.fn(),
  updateAgent: vi.fn(),
}));
vi.mock("../../services/agentService", () => ({
  getAgent: mocks.getAgent,
  updateAgent: mocks.updateAgent,
  getActivity: vi.fn(), getAgentAnalytics: vi.fn(), getAgentEvaluations: vi.fn(), getAgentExecutions: vi.fn(), getAgentOptions: vi.fn(), getAssignments: vi.fn(), getEffectiveAccess: vi.fn(), getVersions: vi.fn(), lifecycleAgent: vi.fn(), saveAssignments: vi.fn(),
}));
vi.mock("../../components/agents/AgentDeletionDialog", () => ({ default: () => null }));

const agent = {
  id: "agent-1", name: "Delivery Agent", slug: "delivery-agent", description: "Current description", owner_id: "owner-1", lifecycle_status: "draft", operational_health: "unknown", current_version: 1, published_version: null, lock_version: 4, instructions: "Use evidence", execution_limits: { max_steps: 20, timeout_seconds: 120 }, environment_restrictions: ["development"], permissions: { edit: true, delete: true, archive: true },
};

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[{ pathname: "/agents/agent-1/configuration", state: { from: "/agents?status=draft" } }]}><Routes><Route path="/agents/:agentId/:tab" element={<AgentWorkspacePage />} /><Route path="/agents" element={<p>Directory</p>} /></Routes></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); mocks.getAgent.mockResolvedValue(agent); });

describe("Agent editor", () => {
  it("loads persisted fields and saves through optimistic concurrency", async () => {
    mocks.updateAgent.mockResolvedValue({ ...agent, name: "Updated Agent", lock_version: 5 });
    setup();
    const name = await screen.findByLabelText("Name");
    expect(name).toHaveValue("Delivery Agent");
    fireEvent.change(name, { target: { value: "Updated Agent" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(mocks.updateAgent).toHaveBeenCalledWith("agent-1", expect.objectContaining({ name: "Updated Agent", owner_id: "owner-1" }), 4));
  });

  it("shows a safe conflict error", async () => {
    mocks.updateAgent.mockRejectedValue({ response: { status: 409 } });
    setup();
    fireEvent.change(await screen.findByLabelText("Name"), { target: { value: "Conflicting Agent" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Refresh before saving");
  });
});
