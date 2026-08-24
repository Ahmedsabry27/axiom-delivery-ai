import fs from "node:fs";
import { expect, test } from "@playwright/test";

type E2EState = { token:string; cross_tenant_token:string; raid_id:string; evidence_id:string; project_id:string; sprint_id:string; actor:string };
const statePath=process.env.E2E_STATE_PATH;
if(!statePath)throw new Error("E2E_STATE_PATH is required");
const state=JSON.parse(fs.readFileSync(statePath,"utf8")) as E2EState;
const apiBase=process.env.VITE_API_URL||"http://127.0.0.1:8000";

test.beforeEach(async({page})=>{await page.addInitScript(token=>window.sessionStorage.setItem("e2e_access_token",token),state.token)});

test("persisted RAID journey remains human-reviewed, evidence-backed, and durable",async({page,request})=>{
  const headers={Authorization:`Bearer ${state.token}`};
  const candidateResponse=await request.post(`${apiBase}/api/raid/detected`,{headers,data:{candidate_type:"RISK",title:`Payment certification window ${test.info().project.name}`,description:"Synthetic sprint evidence indicates a certification-window risk for human review.",confidence:.86,evidence_ids:[state.evidence_id],affected_entities:[{type:"SPRINT",id:state.sprint_id}],suggested_owner:state.actor,suggested_due_date:"2026-08-20",suggested_probability:"LIKELY",suggested_impact:"HIGH",project_id:state.project_id,limitations:["Single synthetic reporting period"]}});
  expect(candidateResponse.status()).toBe(201);
  await page.goto("/raid");
  await expect(page.getByRole("heading",{name:"RAID Intelligence"})).toBeVisible();
  await expect(page.getByRole("button",{name:/Critical risks: 1/})).toBeVisible();
  await page.getByRole("tab",{name:"Risks"}).click();
  await page.getByRole("button",{name:/Review (R-031|item)/}).first().click();
  const detail=page.getByRole("dialog",{name:"R-031"});
  await expect(detail).toContainText("Payment API delay");
  await expect(detail).toContainText("CRITICAL");
  await expect(detail).toContainText(state.actor);
  await expect(detail).toContainText("THREATENS");
  await expect(detail).toContainText("SPRINT");
  await expect(detail).toContainText("Identity provider delivery delayed");
  await detail.getByRole("button",{name:"Add review note"}).click();
  await detail.getByLabel("Review note").fill("Reviewed during the authenticated RAID journey.");
  const reviewSaved=page.waitForResponse(response=>response.url().includes(`/api/raid/${state.raid_id}/review`)&&response.request().method()==="POST");
  await detail.getByRole("button",{name:"Save review"}).click();
  expect((await reviewSaved).status()).toBe(201);
  await expect(page.getByText("Review note saved to durable history.")).toBeVisible();
  await detail.getByRole("button",{name:"Close RAID item"}).click();
  const criticalCell=page.getByRole("gridcell",{name:/ALMOST CERTAIN probability, CRITICAL impact: 1 risks/});
  await criticalCell.focus();
  await criticalCell.press("Enter");
  await expect(page.getByText(/selected ALMOST CERTAIN × CRITICAL cell/)).toBeVisible();

  await expect(page.getByRole("heading",{name:"Detected RAID candidate"})).toBeVisible();
  const acceptedResponse=page.waitForResponse(response=>response.url().includes("/api/raid/detected/")&&response.url().endsWith("/accept")&&response.request().method()==="POST");
  await page.getByRole("button",{name:"Review and edit"}).click();
  await page.getByLabel("Reviewed title").fill(`Payment certification window reviewed ${test.info().project.name}`);
  await page.getByRole("button",{name:"Accept edited candidate"}).click();
  const accepted=await acceptedResponse;
  expect(accepted.status()).toBe(201);
  const acceptedBody=await accepted.json();
  const acceptedId=acceptedBody.item.id as string;
  expect(acceptedBody.item.name).toContain("reviewed");
  await expect(page.getByText(/accepted after human review/)).toBeVisible();

  const conversation=await request.post(`${apiBase}/conversations`,{headers,data:{title:"RAID browser review"}});
  expect(conversation.ok()).toBeTruthy();
  const conversationId=(await conversation.json()).id as string;
  const copilot=await request.post(`${apiBase}/api/raid/copilot`,{headers,data:{conversation_id:conversationId,question:"Show the authorized evidence for this RAID item.",raid_id:acceptedId}});
  expect(copilot.status()).toBe(200);
  const answer=await copilot.json();
  expect(answer.evidence.map((item:{id:string})=>item.id)).toContain(state.evidence_id);
  expect(answer.externalWrites).toBe(false);

  await page.goto(`/raid/${acceptedId}`);
  const acceptedDetail=page.getByRole("dialog");
  await expect(acceptedDetail).toContainText("Payment certification window reviewed");
  await acceptedDetail.getByRole("button",{name:"Propose intervention"}).click();
  await acceptedDetail.getByLabel("Draft intervention").fill("Draft a fictional escalation for human approval.");
  const proposalSaved=page.waitForResponse(response=>response.url().endsWith(`/api/raid/${acceptedId}/proposals`)&&response.request().method()==="POST");
  await acceptedDetail.getByRole("button",{name:"Save as proposed"}).click();
  const proposal=await proposalSaved;
  expect(proposal.status()).toBe(201);
  expect((await proposal.json()).externalWrites).toBe(false);
  await page.reload();
  await expect(page.getByRole("dialog")).toContainText("Draft a fictional escalation for human approval.");
  await expect(page.getByRole("dialog")).toContainText("PROPOSED INTERVENTION CREATED");
});

test("cross-tenant identity cannot discover, relate, accept, or propose against tenant A RAID",async({request})=>{
  const headers={Authorization:`Bearer ${state.cross_tenant_token}`};
  expect((await request.get(`${apiBase}/api/raid/${state.raid_id}`,{headers})).status()).toBe(404);
  const search=await request.get(`${apiBase}/api/raid`,{headers,params:{search:"Payment API delay"}});
  expect(search.status()).toBe(200);
  expect((await search.json()).total).toBe(0);
  expect((await request.post(`${apiBase}/api/raid/${state.raid_id}/evidence`,{headers,data:{evidence_id:state.evidence_id}})).status()).toBe(404);
  expect((await request.post(`${apiBase}/api/raid/${state.raid_id}/relationships`,{headers,data:{entity_type:"SPRINT",entity_id:state.sprint_id,relationship_type:"AFFECTS"}})).status()).toBe(403);
  expect((await request.post(`${apiBase}/api/raid/detected/not-authorized/accept`,{headers,data:{project_id:state.project_id,review_date:"2026-08-20"}})).status()).toBe(403);
  expect((await request.post(`${apiBase}/api/raid/${state.raid_id}/proposals`,{headers,data:{action_type:"DRAFT_ESCALATION",content:"Forbidden cross-tenant draft",status:"PROPOSED"}})).status()).toBe(403);
});
