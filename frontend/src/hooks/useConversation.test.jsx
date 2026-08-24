import {act,renderHook,waitFor} from "@testing-library/react";
import {beforeEach,describe,expect,it,vi} from "vitest";

const mocks=vi.hoisted(()=>({
  getConversations:vi.fn(),
  getConversationMessages:vi.fn(),
  createConversation:vi.fn(),
  deleteConversation:vi.fn(),
  updateConversation:vi.fn(),
}));

vi.mock("../services/conversationService",()=>mocks);

import useConversation from "./useConversation";

describe("useConversation ChatPage API state",()=>{
  beforeEach(()=>{
    vi.clearAllMocks();
    mocks.getConversations.mockResolvedValue([]);
    mocks.getConversationMessages.mockResolvedValue([]);
  });

  it("loads the authoritative conversation array",async()=>{
    mocks.getConversations.mockResolvedValueOnce([
      {id:"conversation-1",title:"existing CHAT",updated_at:"2026-08-12T10:00:00Z"},
    ]);
    const {result}=renderHook(()=>useConversation());
    await waitFor(()=>expect(result.current.conversations).toHaveLength(1));
    expect(result.current.error).toBeNull();
    expect(result.current.conversations).toEqual([
      expect.objectContaining({id:"conversation-1",title:"Existing Chat"}),
    ]);
  });

  it("keeps prior data and exposes an error when refresh fails",async()=>{
    mocks.getConversations.mockResolvedValueOnce([
      {id:"conversation-1",title:"Existing",updated_at:"2026-08-12T10:00:00Z"},
    ]);
    const {result}=renderHook(()=>useConversation());
    await waitFor(()=>expect(result.current.conversations).toHaveLength(1));
    mocks.getConversations.mockRejectedValueOnce(Object.assign(
      new Error("Network Error"),{config:{url:"/conversations"}},
    ));
    await act(()=>result.current.refreshConversations());
    expect(result.current.error).toBe("Conversations could not be loaded.");
    expect(result.current.conversations).toHaveLength(1);
  });

  it("represents a successful empty list without an error",async()=>{
    const {result}=renderHook(()=>useConversation());
    await waitFor(()=>expect(mocks.getConversations).toHaveBeenCalledOnce());
    await waitFor(()=>expect(result.current.loading).toBe(false));
    expect(result.current.conversations).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it("creates a conversation and restores its messages through production services",async()=>{
    mocks.createConversation.mockResolvedValue({
      id:"conversation-2",title:"New Conversation",
    });
    mocks.getConversationMessages.mockResolvedValue([
      {id:"message-1",role:"user",content:"What is edge computing?"},
    ]);
    const {result}=renderHook(()=>useConversation());
    await waitFor(()=>expect(mocks.getConversations).toHaveBeenCalledOnce());
    let id;
    await act(async()=>{id=await result.current.ensureConversation();});
    expect(id).toBe("conversation-2");
    let messages;
    await act(async()=>{messages=await result.current.openConversation(id);});
    expect(mocks.createConversation).toHaveBeenCalledWith("New Conversation");
    expect(mocks.getConversationMessages).toHaveBeenCalledWith("conversation-2");
    expect(messages).toEqual([
      {id:"message-1",role:"user",content:"What is edge computing?"},
    ]);
  });
});
