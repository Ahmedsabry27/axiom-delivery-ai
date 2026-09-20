import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AgentDeletionDialog from "./AgentDeletionDialog";

const mocks = vi.hoisted(() => ({
  deleteAgent: vi.fn(),
  getAgentDeletionImpact: vi.fn(),
  lifecycleAgent: vi.fn(),
}));
vi.mock("../../services/agentService", () => mocks);

const agent = { id: "agent-1", name: "Delivery Agent", lifecycle_status: "draft", lock_version: 3 };
function setup(onCompleted = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><AgentDeletionDialog agent={agent} open onOpenChange={vi.fn()} onCompleted={onCompleted} /></QueryClientProvider>);
  return onCompleted;
}

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("Agent deletion impact dialog", () => {
  it("permanently deletes an eligible unused draft", async () => {
    mocks.getAgentDeletionImpact.mockResolvedValue({ eligible_for_permanent_deletion: true, permissions: { delete: true }, reasons: [] });
    mocks.deleteAgent.mockResolvedValue({});
    const completed = setup();
    fireEvent.click(await screen.findByRole("button", { name: "Delete permanently" }));
    await waitFor(() => expect(mocks.deleteAgent).toHaveBeenCalledWith("agent-1"));
    expect(completed).toHaveBeenCalledWith("deleted");
  });

  it("archives an agent with retained history", async () => {
    mocks.getAgentDeletionImpact.mockResolvedValue({ eligible_for_permanent_deletion: false, permissions: { archive: true }, reasons: ["Agent has execution history"], active_execution_count: 0 });
    mocks.lifecycleAgent.mockResolvedValue({});
    const completed = setup();
    const archiveButton = await screen.findByRole("button", { name: "Archive agent" });
    await waitFor(() => expect(archiveButton).toBeEnabled());
    fireEvent.click(archiveButton);
    await waitFor(() => expect(mocks.lifecycleAgent).toHaveBeenCalledWith("agent-1", "archive", 3, expect.objectContaining({ confirmed: true })));
    expect(completed).toHaveBeenCalledWith("archived");
  });

  it("keeps the dialog open and reports a failed deletion", async () => {
    mocks.getAgentDeletionImpact.mockResolvedValue({ eligible_for_permanent_deletion: true, permissions: { delete: true }, reasons: [] });
    mocks.deleteAgent.mockRejectedValue({ response: { data: { detail: { message: "Deletion was rejected" } } } });
    const completed = setup();
    fireEvent.click(await screen.findByRole("button", { name: "Delete permanently" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Deletion was rejected");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(completed).not.toHaveBeenCalled();
  });
});
