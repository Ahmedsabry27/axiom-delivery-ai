import fs from "node:fs";
import {expect,test} from "@playwright/test";

type E2EState={requester_token:string;cross_tenant_token:string};
const statePath=process.env.E2E_STATE_PATH;
if(!statePath)throw new Error("E2E_STATE_PATH is required");
const state=JSON.parse(fs.readFileSync(statePath,"utf8")) as E2EState;
const apiBase=process.env.VITE_API_URL||"http://127.0.0.1:8000";
const auth=(token:string)=>({Authorization:`Bearer ${token}`});

test.beforeEach(async({page})=>{
  await page.addInitScript(token=>window.sessionStorage.setItem("e2e_access_token",token),state.requester_token);
});

test("authorized transcript becomes grounded, reviewed, durable proposals",async({page,request})=>{
  await page.goto("/meetings/new");
  await expect(page.getByRole("heading",{name:"New Meeting"})).toBeVisible();
  await page.getByLabel("Meeting title").fill("Synthetic release review");
  await page.getByLabel("Transcript or meeting notes").fill([
    "Ahmed: We decided to proceed with Release 4.",
    "Sarah: I will publish the readiness pack Friday.",
    "Omar: Risk: supplier certification may delay launch.",
    "Lina: The launch depends on security approval.",
  ].join("\n"));
  await expect(page.getByRole("button",{name:"Save and Analyse"})).toBeDisabled();
  await page.getByLabel("Authorized to process").check();
  const analysed=page.waitForResponse(response=>response.url().endsWith("/analyse")&&response.status()===200);
  await page.getByRole("button",{name:"Save and Analyse"}).click();
  await analysed;
  await expect(page).toHaveURL(/\/meetings\/[^/]+\/review$/);
  const meetingId=page.url().match(/\/meetings\/([^/]+)\/review$/)?.[1];
  expect(meetingId).toBeTruthy();
  await expect(page.getByText("4 findings need review")).toBeVisible();

  const decision=page.locator("article").filter({hasText:"DECISION"}).filter({hasText:"proceed with Release 4"});
  await decision.getByRole("button").click();
  await expect(page.locator("article.bg-red-50")).toContainText("proceed with Release 4");
  await page.getByRole("button",{name:/Accept/}).click();
  await expect(decision.getByText("ACCEPTED")).toBeVisible();
  await decision.getByRole("button",{name:"Create governed proposal"}).click();
  await expect(decision.getByRole("link",{name:"Open proposal"})).toBeVisible();

  await page.reload();
  await expect(decision.getByRole("link",{name:"Open proposal"})).toBeVisible();
  const hidden=await request.get(`${apiBase}/api/meetings/${meetingId}`,{headers:auth(state.cross_tenant_token)});
  expect(hidden.status()).toBe(404);
  const duplicate=await request.post(`${apiBase}/api/meetings/${meetingId}/analyse`,{headers:auth(state.requester_token)});
  expect(duplicate.status()).toBe(200);
  const findings=await request.get(`${apiBase}/api/meetings/${meetingId}/findings`,{headers:auth(state.requester_token)});
  expect((await findings.json()).items).toHaveLength(4);
});
