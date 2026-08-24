import fs from "node:fs";
import {expect,test} from "@playwright/test";

type E2EState={
  token:string;cross_tenant_token:string;requester_token:string;approver_token:string;
  executor_token:string;verifier_token:string;requester_id:string;approver_id:string;
  actor:string;project_id:string;evidence_id:string;expired_approval_id:string;stale_approval_id:string;
};
const statePath=process.env.E2E_STATE_PATH;
if(!statePath)throw new Error("E2E_STATE_PATH is required");
const state=JSON.parse(fs.readFileSync(statePath,"utf8")) as E2EState;
const apiBase=process.env.VITE_API_URL||"http://127.0.0.1:8000";
const auth=(token:string)=>({Authorization:`Bearer ${token}`});
const switchIdentity=async(page:import("@playwright/test").Page,token:string)=>{
  await page.evaluate(value=>{
    window.localStorage.setItem("e2e_access_token_override",value);
    window.sessionStorage.setItem("e2e_access_token",value);
  },token);
};

test.beforeEach(async({page})=>{
  await page.addInitScript(token=>window.sessionStorage.setItem(
    "e2e_access_token",
    window.localStorage.getItem("e2e_access_token_override")||token,
  ),state.requester_token);
});

test("requester to approver to executor to verifier is durable and exactly once",async({page,request})=>{
  await page.goto("/actions");
  await expect(page.getByRole("heading",{name:"Action Center"})).toBeVisible();
  await page.getByRole("button",{name:"Propose action"}).click();
  await page.getByLabel("Title").fill("Browser-proven supplier risk");
  await page.getByLabel("Description").fill("A persisted, evidence-backed action created through the authenticated UI.");
  await page.getByLabel("Approved payload (JSON)").fill(JSON.stringify({
    project_id:state.project_id,item_type:"RISK",name:"Browser-proven supplier risk",
    description:"Synthetic supplier readiness could delay delivery.",probability:"LIKELY",
    impact:"HIGH",review_date:"2026-08-22",
  }));
  await page.getByLabel(/Evidence IDs/).fill(state.evidence_id);
  const createdResponse=page.waitForResponse(response=>response.url().endsWith("/api/actions")&&response.request().method()==="POST");
  await page.getByRole("button",{name:"Create draft"}).click();
  const created=await createdResponse;
  expect(created.status()).toBe(201);
  const action=await created.json() as {id:string};
  await expect(page).toHaveURL(new RegExp(`/actions/${action.id}$`));
  await expect(page.getByText("Supplier review",{exact:false}).or(page.getByText("Identity provider delivery delayed"))).toBeVisible();

  await page.getByLabel("Assigned approver").fill(state.approver_id);
  const submittedResponse=page.waitForResponse(response=>response.url().endsWith(`/api/actions/${action.id}/submit`));
  await page.getByRole("button",{name:"submit"}).click();
  const submitted=await submittedResponse;
  expect(submitted.status()).toBe(200);
  const approval=await submitted.json() as {id:string};

  await switchIdentity(page,state.approver_token);
  await page.goto(`/approvals/${approval.id}`);
  await expect(page.getByText("What will change")).toBeVisible();
  await expect(page.getByText("Identity provider delivery delayed")).toBeVisible();
  await page.getByLabel("Decision rationale").fill("Evidence, target, and exact payload reviewed in the browser journey.");
  const approvedResponse=page.waitForResponse(response=>response.url().endsWith(`/api/approvals/${approval.id}/approve`));
  await page.getByRole("button",{name:/Approve/}).click();
  expect((await approvedResponse).status()).toBe(200);

  await switchIdentity(page,state.executor_token);
  await page.goto(`/actions/${action.id}`);
  const executionResponse=page.waitForResponse(response=>response.url().endsWith(`/api/actions/${action.id}/execute`));
  await page.getByRole("button",{name:"execute"}).click();
  const execution=await executionResponse;
  expect(execution.status()).toBe(200);
  const executionBody=await execution.json() as {id:string};
  const executionKey=(execution.request().postDataJSON() as {idempotency_key:string}).idempotency_key;
  const replay=await request.post(`${apiBase}/api/actions/${action.id}/execute`,{headers:auth(state.executor_token),data:{idempotency_key:executionKey}});
  expect(replay.status()).toBe(200);
  expect((await replay.json()).id).toBe(executionBody.id);

  await switchIdentity(page,state.verifier_token);
  await page.goto(`/actions/${action.id}`);
  await page.getByLabel("Transition comment").fill("Independent system-of-record read completed.");
  const verifiedResponse=page.waitForResponse(response=>response.url().endsWith(`/api/actions/${action.id}/verify`));
  await page.getByRole("button",{name:"verify",exact:true}).click();
  expect((await verifiedResponse).status()).toBe(200);
  await expect(page.getByLabel("Action detail").getByText("VERIFIED",{exact:true})).toBeVisible();
  await expect(page.getByText("action.verified")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Action detail").getByText("VERIFIED",{exact:true})).toBeVisible();
  const persisted=await request.get(`${apiBase}/api/actions/${action.id}`,{headers:auth(state.verifier_token)});
  expect(persisted.status()).toBe(200);
  const persistedBody=await persisted.json();
  expect(persistedBody.status).toBe("VERIFIED");
  expect(persistedBody.executions).toHaveLength(1);
  expect(persistedBody.auditTrail.map((item:{action:string})=>item.action)).toContain("action.verified");
});

test("unsafe decisions, stale or expired approvals, missing evidence, and tenant leaks fail closed",async({request})=>{
  const requesterHeaders=auth(state.requester_token);
  const noEvidence=await request.post(`${apiBase}/api/actions`,{headers:requesterHeaders,data:{action_type:"CREATE_RAID_ITEM",title:"Evidence negative",payload:{project_id:state.project_id}}});
  expect(noEvidence.status()).toBe(201);
  const noEvidenceId=(await noEvidence.json()).id as string;
  const missing=await request.post(`${apiBase}/api/actions/${noEvidenceId}/submit`,{headers:requesterHeaders,data:{assigned_approver_id:state.approver_id}});
  expect(missing.status()).toBe(422);
  expect((await missing.json()).detail.code).toBe("EVIDENCE_REQUIRED");

  const selfAction=await request.post(`${apiBase}/api/actions`,{headers:auth(state.token),data:{action_type:"CREATE_RAID_ITEM",title:"Self approval negative",payload:{project_id:state.project_id},evidence_ids:[state.evidence_id]}});
  const selfActionId=(await selfAction.json()).id as string;
  const selfRequest=await request.post(`${apiBase}/api/actions/${selfActionId}/submit`,{headers:auth(state.token),data:{assigned_approver_id:state.actor}});
  const selfApprovalId=(await selfRequest.json()).id as string;
  const selfDecision=await request.post(`${apiBase}/api/approvals/${selfApprovalId}/approve`,{headers:auth(state.token),data:{comment:"Must fail"}});
  expect(selfDecision.status()).toBe(403);
  expect((await selfDecision.json()).detail.code).toBe("SEPARATION_OF_DUTIES");

  const expired=await request.post(`${apiBase}/api/approvals/${state.expired_approval_id}/approve`,{headers:auth(state.approver_token),data:{comment:"Too late"}});
  expect(expired.status()).toBe(409);
  expect((await expired.json()).detail.code).toBe("APPROVAL_EXPIRED");
  const stale=await request.post(`${apiBase}/api/approvals/${state.stale_approval_id}/approve`,{headers:auth(state.approver_token),data:{comment:"Old version"}});
  expect(stale.status()).toBe(409);
  expect((await stale.json()).detail.code).toBe("STALE_ACTION_VERSION");
  const hidden=await request.get(`${apiBase}/api/actions/${selfActionId}`,{headers:auth(state.cross_tenant_token)});
  expect(hidden.status()).toBe(404);
});
