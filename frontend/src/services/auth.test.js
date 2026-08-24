import { beforeEach, describe, expect, it, vi } from "vitest";

const amplifyAuth = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  fetchAuthSession: vi.fn(),
  signInWithRedirect: vi.fn(),
  signOut: vi.fn(),
}));
vi.mock("aws-amplify/auth",()=>amplifyAuth);
vi.mock("../config/amplify",()=>({isLocalAuthBypass:true}));

describe("local authentication fallback",()=>{
  beforeEach(()=>vi.clearAllMocks());
  it("provides a local identity without calling Cognito",async()=>{
    const auth=await import("./auth");
    expect(await auth.currentUser()).toMatchObject({userId:"local-developer"});
    expect((await auth.getSession()).tokens.idToken.payload).toMatchObject({
      email:"ahmedsabry27@outlook.com",
      name:"Ahmed Sabry",
      given_name:"Ahmed",
      family_name:"Sabry",
    });
    expect(await auth.getAccessToken()).toBeNull();
    expect(amplifyAuth.getCurrentUser).not.toHaveBeenCalled();
  });
});
