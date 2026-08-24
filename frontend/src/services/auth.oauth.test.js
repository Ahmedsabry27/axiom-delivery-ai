import { beforeEach, describe, expect, it, vi } from "vitest";

const amplifyAuth = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  fetchAuthSession: vi.fn(),
  signInWithRedirect: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("aws-amplify/auth", () => amplifyAuth);
vi.mock("../config/amplify", () => ({ isLocalAuthBypass: false }));

describe("Cognito OAuth callback completion", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/");
  });

  it("waits for the access token instead of starting a second login redirect", async () => {
    window.history.replaceState({}, "", "/?code=authorization-code&state=valid-state");
    amplifyAuth.getCurrentUser
      .mockRejectedValueOnce(new Error("session exchange pending"))
      .mockResolvedValue({ username: "ahmed", userId: "user-1" });
    amplifyAuth.fetchAuthSession
      .mockRejectedValueOnce(new Error("session exchange pending"))
      .mockResolvedValue({ tokens: { accessToken: { toString: () => "access-token" } } });

    const auth = await import("./auth");
    await expect(auth.currentUser()).resolves.toMatchObject({ userId: "user-1" });
    expect(amplifyAuth.getCurrentUser).toHaveBeenCalledTimes(2);
    expect(amplifyAuth.signInWithRedirect).not.toHaveBeenCalled();
  });

  it("rejects an unauthenticated non-callback request immediately", async () => {
    amplifyAuth.getCurrentUser.mockRejectedValue(new Error("not authenticated"));
    amplifyAuth.fetchAuthSession.mockRejectedValue(new Error("not authenticated"));

    const auth = await import("./auth");
    await expect(auth.currentUser()).rejects.toThrow("not authenticated");
    expect(amplifyAuth.getCurrentUser).toHaveBeenCalledTimes(1);
  });
});
