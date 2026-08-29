import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  delete: vi.fn(),
  get: vi.fn(),
  patch: vi.fn(),
  post: vi.fn(),
}));

vi.mock("../services/api", () => ({ default: api }));

import { updateConversationTitle } from "./conversationApi";

describe("conversationApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("updates a conversation through the shared relative API client", async () => {
    api.patch.mockResolvedValue({ data: { id: "conversation-1", title: "Hello" } });

    const result = await updateConversationTitle("conversation-1", "Hello");

    expect(api.patch).toHaveBeenCalledWith(
      "/conversations/conversation-1",
      { title: "Hello" },
    );
    expect(result.title).toBe("Hello");
  });
});
