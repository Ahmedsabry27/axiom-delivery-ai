import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  continueRuntime: vi.fn(),
  continueRuntimeMessage: vi.fn(),
  startExecution: vi.fn(),
  subscribeRuntime: vi.fn(),
  getRuntime: vi.fn(),
  unsubscribe: vi.fn(),
}));

vi.mock("../api/conversationApi", () => ({
  updateConversationTitle: vi.fn(),
}));

vi.mock("../services/chat.service", () => ({
  startExecution: mocks.startExecution,
}));

vi.mock("../services/runtime.service", () => ({
  approveRuntime: vi.fn(),
  cancelRuntime: vi.fn(),
  continueRuntime: mocks.continueRuntime,
  continueRuntimeMessage: mocks.continueRuntimeMessage,
  denyRuntime: vi.fn(),
  getConversationRuntime: vi.fn(),
  getRuntime: mocks.getRuntime,
  subscribeRuntime: mocks.subscribeRuntime,
}));

import useChat from "./useChat";

describe("useChat runtime continuation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.subscribeRuntime.mockReturnValue(mocks.unsubscribe);
    mocks.startExecution.mockResolvedValue({
      execution_id: "execution-1",
      workflow_id: "workflow-1",
      status: "RUNNING",
    });
    mocks.continueRuntime.mockResolvedValue({
      execution_id: "execution-1",
      workflow_id: "workflow-1",
      status: "RUNNING",
    });
    mocks.continueRuntimeMessage.mockResolvedValue({
      execution_id: "execution-1",
      workflow_id: "workflow-1",
      status: "WAITING_FOR_INPUT",
    });
    mocks.getRuntime.mockResolvedValue({
      execution_id:"execution-1",workflow_id:"workflow-1",status:"RUNNING",state_version:3,last_sequence:2,
    });
  });

  it("reconnects to runtime events after submitting required Jira details", async () => {
    const conversation = {
      conversations: [{ id: "conversation-1", title: "Create a Jira ticket" }],
      ensureConversation: vi.fn().mockResolvedValue("conversation-1"),
      refreshConversations: vi.fn(),
    };
    const { result } = renderHook(() => useChat(conversation));

    await act(() => result.current.handleStream("Create a Jira ticket"));

    const firstEvent = mocks.subscribeRuntime.mock.calls[0][1];
    act(() => firstEvent({
      type: "required_input",
      execution_id: "execution-1",
      workflow_id: "workflow-1",
      sequence: 2,
      state_version: 2,
      aggregate_status: "WAITING_FOR_INPUT",
      continuation_id: "continuation-1",
      fields: [{ name: "project_key", required: true }],
      status: "waiting",
    }));

    await act(() => result.current.resumeAgentExecution({ project_key: "OPS" }));

    expect(mocks.continueRuntime).toHaveBeenCalledWith(
      "execution-1",
      "continuation-1",
      { project_key: "OPS" },
    );
    expect(mocks.unsubscribe).toHaveBeenCalled();
    expect(mocks.subscribeRuntime).toHaveBeenCalledTimes(2);
    expect(mocks.subscribeRuntime.mock.calls[1][0]).toBe("execution-1");

    const replayedEvent = mocks.subscribeRuntime.mock.calls[1][1];
    act(() => replayedEvent({
      type: "required_input",
      continuation_id: "continuation-1",
      fields: [{ name: "project_key", required: true }],
      status: "waiting",
    }));

    expect(result.current.activeExecution.continuation).toBeNull();
    expect(result.current.loading).toBe(true);
  });

  it("routes conversational input to the active continuation without a second execution", async () => {
    const conversation = {
      conversations: [{ id: "conversation-1", title: "Create a Jira ticket" }],
      ensureConversation: vi.fn().mockResolvedValue("conversation-1"),
      refreshConversations: vi.fn(),
    };
    const { result } = renderHook(() => useChat(conversation));
    await act(() => result.current.handleStream("Create a Jira ticket"));
    const receive = mocks.subscribeRuntime.mock.calls[0][1];
    act(() => receive({
      type: "required_input", execution_id: "execution-1", workflow_id: "workflow-1",
      continuation_id: "continuation-1", fields: [{ name: "summary", required: true }],
      aggregate_status: "WAITING_FOR_INPUT", status: "waiting",
    }));
    await act(() => result.current.resumeAgentExecution(
      { natural_language: "Payment API timeout" }, "natural_language",
    ));
    expect(mocks.continueRuntimeMessage).toHaveBeenCalledWith(
      "execution-1", "continuation-1", "Payment API timeout",
    );
    expect(mocks.continueRuntime).not.toHaveBeenCalled();
    expect(mocks.startExecution).toHaveBeenCalledTimes(1);
  });

  it("switches runtime and SSE ownership after a backend new-request handoff", async () => {
    const conversation = {
      conversations: [{ id: "conversation-1", title: "Jira report" }],
      ensureConversation: vi.fn().mockResolvedValue("conversation-1"),
      refreshConversations: vi.fn(),
    };
    const { result } = renderHook(() => useChat(conversation));
    await act(() => result.current.handleStream("Generate Jira report"));
    const oldReceive = mocks.subscribeRuntime.mock.calls[0][1];
    act(() => oldReceive({
      type: "required_input", execution_id: "execution-1", workflow_id: "workflow-1",
      continuation_id: "continuation-1", fields: [{ name: "jira_report_scope" }],
      aggregate_status: "WAITING_FOR_INPUT", status: "waiting",
    }));
    mocks.continueRuntimeMessage.mockResolvedValueOnce({
      outcome: "new_request",
      cancelled_execution_id: "execution-1",
      execution: {
        execution_id: "execution-2", workflow_id: "workflow-2", status: "RUNNING",
        continuation: null,
      },
    });
    mocks.getRuntime.mockResolvedValueOnce({
      execution_id: "execution-2", workflow_id: "workflow-2", status: "RUNNING",
      state_version: 1, last_sequence: 0, continuation: null,
    });

    await act(() => result.current.resumeAgentExecution(
      { natural_language: "Create a Jira ticket" }, "natural_language",
    ));

    expect(result.current.activeExecution.execution_id).toBe("execution-2");
    expect(result.current.activeExecution.continuation).toBeNull();
    expect(mocks.subscribeRuntime.mock.calls[1][0]).toBe("execution-2");
    expect(mocks.unsubscribe).toHaveBeenCalled();

    act(() => oldReceive({
      type: "required_input", execution_id: "execution-1",
      continuation_id: "continuation-1", aggregate_status: "WAITING_FOR_INPUT",
      fields: [{ name: "jira_report_scope" }], status: "waiting",
    }));
    expect(result.current.activeExecution.execution_id).toBe("execution-2");
    expect(result.current.activeExecution.continuation).toBeNull();
  });
});
