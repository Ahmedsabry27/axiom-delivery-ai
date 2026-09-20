import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AgentsPage from "./AgentsPage";

const mocks = vi.hoisted(() => ({ useAgents: vi.fn(), lifecycleAgent: vi.fn() }));
vi.mock("../../hooks/useAgents", () => ({ useAgents: mocks.useAgents }));
vi.mock("../../services/agentService", () => ({ lifecycleAgent: mocks.lifecycleAgent }));
vi.mock("../../components/agents/AgentDeletionDialog", () => ({
  default: ({ agent, open, onCompleted }) => open ? <div role="dialog">Deletion impact for {agent.name}<button onClick={() => onCompleted("deleted")}>Confirm test deletion</button></div> : null,
}));
vi.mock("../../components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onSelect }) => <button onClick={onSelect}>{children}</button>,
  DropdownMenuSeparator: () => <hr />,
  DropdownMenuTrigger: ({ children }) => children,
}));

const agent = {
  id: "agent-1",
  name: "Delivery Agent",
  slug: "delivery-agent",
  description: "Evidence-led delivery",
  lifecycle_status: "draft",
  operational_health: "unknown",
  current_version: 1,
  owner_id: "owner-1",
  model: "gpt-4.1-mini",
  tool_count: 2,
  knowledge_count: 1,
  execution_count: 0,
  success_rate: null,
  last_execution_at: null,
  updated_at: "2026-08-31T10:00:00Z",
  lock_version: 1,
  permissions: { edit: true, delete: true, archive: true },
};

function setup(overrides = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  mocks.useAgents.mockReturnValue({
    data: { items: [{ ...agent, ...overrides }], total: 1, page: 1, pages: 1, permissions: { create: true } },
    dataUpdatedAt: Date.now(),
    isLoading: false,
    isFetching: false,
    refetch: vi.fn(),
  });
  return { ...render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={["/agents?status=draft"]}><AgentsPage /></MemoryRouter></QueryClientProvider>), queryClient };
}

beforeEach(() => vi.clearAllMocks());

describe("Agents directory actions", () => {
  it("shows labelled filters, readable capabilities and discoverable actions", () => {
    setup();
    expect(screen.getByText("Search agents")).toBeInTheDocument();
    expect(screen.getAllByText("2 tools · 1 sources").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Actions for Delivery Agent" })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /Edit/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /Delete or archive/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Never").length).toBeGreaterThan(0);
  });

  it("opens the governed deletion flow, retains the row, then refreshes counts", async () => {
    const { queryClient } = setup();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    fireEvent.click(screen.getAllByRole("button", { name: /Delete or archive/ })[0]);
    expect(screen.getByRole("dialog")).toHaveTextContent("Deletion impact for Delivery Agent");
    expect(screen.getAllByText("Delivery Agent").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Confirm test deletion" }));
    await vi.waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["agents"] }));
  });

  it("hides unauthorized mutation actions while retaining View", () => {
    setup({ permissions: { edit: false, delete: false, archive: false } });
    expect(screen.queryByRole("button", { name: /Edit/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Delete or archive/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /View/ }).length).toBeGreaterThan(0);
  });
});
