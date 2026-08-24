import crypto from "node:crypto";
import {expect,test} from "@playwright/test";

const apiBase=process.env.VITE_API_URL||"http://127.0.0.1:8000";
const secret=process.env.E2E_AUTH_SECRET;
if(!secret)throw new Error("E2E_AUTH_SECRET is required");
const token=(sub:string,tenant="governance-e2e",extra:Record<string,unknown>={})=>{
  const now=Math.floor(Date.now()/1000);const payload={sub,"custom:tenant_id":tenant,"cognito:groups":["admin"],iss:"ai-delivery-platform-e2e",iat:now,exp:now+600,...extra};
  const encoded=Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `e2e.${encoded}.${crypto.createHmac("sha256",secret).update(encoded).digest("hex")}`;
};
const headers=(value:string)=>({Authorization:`Bearer ${value}`});
const setIdentity=async(page:import("@playwright/test").Page,value:string)=>page.addInitScript(auth=>{window.localStorage.setItem("e2e_access_token_override",auth);window.sessionStorage.setItem("e2e_access_token",auth)},value);

test("governance administrator completes the governed evidence journey",async({page,request},testInfo)=>{
  const suffix=`${testInfo.project.name}-${Date.now()}`;const author=token(`author-${suffix}`);const approver=token(`approver-${suffix}`);
  const created=await request.post(`${apiBase}/api/governance/policies`,{headers:headers(author),data:{policy_key:`model-allowlist-${suffix}`,name:`Model allowlist ${suffix}`,category:"MODEL_ALLOWLIST",conditions:{classification:"CONFIDENTIAL"},effect:{decision:"ALLOW"},reason_codes:["MODEL_APPROVED"]}});
  expect(created.status()).toBe(201);const policy=await created.json() as {id:string};
  const simulation=await request.post(`${apiBase}/api/governance/policies/${policy.id}/simulate`,{headers:headers(author),data:{scenario:{classification:"CONFIDENTIAL",targets:["model"]}}});
  expect(simulation.status()).toBe(200);expect((await simulation.json()).proposed_decision.decision).toBe("ALLOW");
  expect((await request.post(`${apiBase}/api/governance/policies/${policy.id}/submit`,{headers:headers(author)})).status()).toBe(200);
  expect((await request.post(`${apiBase}/api/governance/policies/${policy.id}/activate`,{headers:headers(approver)})).status()).toBe(200);

  const modelResponse=await request.post(`${apiBase}/api/models`,{headers:headers(author),data:{model_key:`browser-${suffix}`,provider:"openai",provider_model_id:`browser-model-${suffix}`,display_name:`Browser model ${suffix}`,model_family:"synthetic",capabilities:["chat"],approved_use_cases:["copilot"],prohibited_use_cases:[],allowed_data_classifications:["INTERNAL"],allowed_regions:["eu"],status:"DRAFT",context_limit:8192}});
  expect(modelResponse.status()).toBe(201);const model=await modelResponse.json() as {id:string};
  expect((await request.patch(`${apiBase}/api/models/${model.id}`,{headers:headers(approver),data:{status:"APPROVED"}})).status()).toBe(200);
  expect((await request.patch(`${apiBase}/api/models/${model.id}`,{headers:headers(approver),data:{status:"ACTIVE"}})).status()).toBe(200);

  const datasetResponse=await request.post(`${apiBase}/api/evaluations/datasets`,{headers:headers(approver),data:{dataset_key:`browser-security-${suffix}`,name:`Browser security ${suffix}`,version:1,status:"APPROVED",use_case:"copilot",cases:[{id:"authorized-source",checks:{schema:true,authorized:true}},{id:"blocked-source",checks:{schema:true,authorized:false}}]}});
  expect(datasetResponse.status()).toBe(201);const dataset=await datasetResponse.json() as {id:string};
  const runResponse=await request.post(`${apiBase}/api/evaluations/runs`,{headers:headers(approver),data:{dataset_id:dataset.id,model_id:model.id}});
  expect(runResponse.status()).toBe(201);const run=await runResponse.json() as {id:string};
  expect((await request.post(`${apiBase}/api/ai-operations/budgets`,{headers:headers(approver),data:{scope_type:"TENANT",scope_id:`governance-e2e-${suffix}`,period:"MONTHLY",soft_limit:"75.00",hard_limit:"100.00",currency:"USD",alert_thresholds:[50,75,90,100],effective_from:new Date().toISOString()}})).status()).toBe(201);
  expect((await request.post(`${apiBase}/api/ai-operations/incidents`,{headers:headers(approver),data:{incident_type:"EVALUATION_REGRESSION",severity:"SEV3",affected_services:["evaluation"],affected_tenant_refs:[],trace_ids:[],impact_summary:"Synthetic browser validation incident"}})).status()).toBe(201);

  await setIdentity(page,approver);await page.goto("/governance");
  await expect(page.getByRole("heading",{name:"Governance"})).toBeVisible();
  await expect(page.getByText("Policy Compliance")).toBeVisible();
  await page.goto("/governance/policies");await expect(page.getByText(`Model allowlist ${suffix}`)).toBeVisible();
  await page.goto(`/governance/policies/${policy.id}`);await expect(page.getByText("ACTIVE",{exact:true})).toBeVisible();
  await page.goto("/governance/permissions");await expect(page.getByText("approvals.approve",{exact:true})).toBeVisible();
  await page.goto("/governance/audit");await expect(page.getByText("policy.activated",{exact:true}).first()).toBeVisible();
  await page.goto("/models");await expect(page.getByText(`Browser model ${suffix}`)).toBeVisible();
  await page.goto("/ai-operations");await expect(page.getByRole("heading",{name:"AI Operations"})).toBeVisible();
  await page.goto(`/ai-operations/evaluations/${run.id}`);await expect(page.getByText(/DETERMINISTIC_GATE_FAILED/)).toBeVisible();
  await page.goto("/ai-operations/costs");await expect(page.getByText("100.00",{exact:true}).first()).toBeVisible();
  await page.goto("/ai-operations/incidents");await expect(page.getByText("EVALUATION_REGRESSION",{exact:true}).first()).toBeVisible();
  await page.reload();await expect(page.getByText("EVALUATION_REGRESSION",{exact:true}).first()).toBeVisible();
});

test("governance security boundaries fail closed",async({request},testInfo)=>{
  const suffix=`${testInfo.project.name}-${Date.now()}`;const author=token(`negative-author-${suffix}`);const normal=token(`normal-${suffix}`,"governance-e2e",{"cognito:groups":[],permissions:["runtime.execute"]});
  const created=await request.post(`${apiBase}/api/governance/policies`,{headers:headers(author),data:{policy_key:`negative-${suffix}`,name:`Negative policy ${suffix}`,category:"AI_USAGE",conditions:{risk:"HIGH"},effect:{decision:"BLOCK"}}});
  const policy=await created.json() as {id:string};await request.post(`${apiBase}/api/governance/policies/${policy.id}/submit`,{headers:headers(author)});
  const service=token(`service-${suffix}`,"governance-e2e",{identity_type:"service"});
  const automated=await request.post(`${apiBase}/api/governance/policies/${policy.id}/activate`,{headers:headers(service)});expect(automated.status()).toBe(403);expect((await automated.json()).detail.code).toBe("HUMAN_AUTHORIZATION_REQUIRED");
  expect((await request.get(`${apiBase}/api/governance/overview`,{headers:headers(normal)})).status()).toBe(403);
  expect((await request.get(`${apiBase}/api/governance/policies/${policy.id}`,{headers:headers(token(`other-${suffix}`,"other-tenant"))})).status()).toBe(404);
  const audit=await request.get(`${apiBase}/api/audit/events`,{headers:headers(author)});const event=(await audit.json()).items[0];
  expect((await request.patch(`${apiBase}/api/audit/events/${event.event_id}`,{headers:headers(author),data:{result:"CHANGED"}})).status()).toBe(405);
  expect((await request.delete(`${apiBase}/api/audit/events/${event.event_id}`,{headers:headers(author)})).status()).toBe(405);
});
