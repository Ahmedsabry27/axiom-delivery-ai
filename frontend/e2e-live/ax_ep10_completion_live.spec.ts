import crypto from "node:crypto";
import {expect,test} from "@playwright/test";

const apiBase=process.env.VITE_API_URL||"http://127.0.0.1:8000";
const secret=process.env.E2E_AUTH_SECRET;
if(!secret)throw new Error("E2E_AUTH_SECRET is required");
const tenant=`ax-ep10-completion-${Date.now()}`;
const token=(sub:string,tenantId=tenant)=>{const now=Math.floor(Date.now()/1000);const payload={sub,"custom:tenant_id":tenantId,"cognito:groups":["admin"],iss:"ai-delivery-platform-e2e",iat:now,exp:now+900};const encoded=Buffer.from(JSON.stringify(payload)).toString("base64url");return `e2e.${encoded}.${crypto.createHmac("sha256",secret).update(encoded).digest("hex")}`};
const auth=(value:string)=>({Authorization:`Bearer ${value}`});
const setIdentity=async(page:import("@playwright/test").Page,value:string)=>page.addInitScript(key=>window.sessionStorage.setItem("e2e_access_token",key),value);
const activateModel=async(request:import("@playwright/test").APIRequestContext,author:string,approver:string,suffix:string)=>{
  const modelResponse=await request.post(`${apiBase}/api/models`,{headers:auth(author),data:{model_key:`completion-${suffix}`,provider:"openai",provider_model_id:"gpt-4.1-mini",display_name:`Completion ${suffix}`,model_family:"controlled",capabilities:["chat"],approved_use_cases:["copilot","agent"],prohibited_use_cases:[],allowed_data_classifications:["INTERNAL"],allowed_regions:["eu"],status:"DRAFT",context_limit:8192}});
  expect(modelResponse.status(),await modelResponse.text()).toBe(201);const model=await modelResponse.json() as {id:string};
  expect((await request.patch(`${apiBase}/api/models/${model.id}`,{headers:auth(approver),data:{status:"APPROVED"}})).status()).toBe(200);
  expect((await request.patch(`${apiBase}/api/models/${model.id}`,{headers:auth(approver),data:{status:"ACTIVE"}})).status()).toBe(200);
  expect((await request.post(`${apiBase}/api/models/${model.id}/prices`,{headers:auth(approver),data:{version:1,input_cost_per_million:"1000",output_cost_per_million:"1000",currency:"USD",effective_from:new Date(Date.now()-60000).toISOString()}})).status()).toBe(201);
  return model;
};

test("Copilot execution reserves, settles, evaluates, audits, and persists",async({page,request},testInfo)=>{
  test.skip(testInfo.project.name!=="live-1440","Cross-module lifecycle runs once; responsive governance coverage runs separately.");
  const suffix=`${testInfo.project.name}-${Date.now()}`;const author=token(`author-${suffix}`);const approver=token(`approver-${suffix}`);
  const model=await activateModel(request,author,approver,suffix);
  const budgetResponse=await request.post(`${apiBase}/api/ai-operations/budgets`,{headers:auth(approver),data:{scope_type:"TENANT",scope_id:tenant,period:"MONTHLY",soft_limit:"0.75",hard_limit:"1.00",currency:"USD",alert_thresholds:[50,75,90,100],effective_from:new Date(Date.now()-60000).toISOString()}});
  expect(budgetResponse.status()).toBe(201);const budget=await budgetResponse.json() as {id:string};
  const agentResponse=await request.post(`${apiBase}/api/v1/agents`,{headers:auth(approver),data:{name:`Deployment reporter ${suffix}`,description:"Controlled native deployment reporting",instructions:"Generate the requested deterministic deployment report.",model_configuration:{provider:"openai",model:"gpt-4.1-mini"},capabilities:["deployment.report.generate"],tool_discovery_configuration:{mode:"assigned_only"}}});
  expect(agentResponse.status(),await agentResponse.text()).toBe(201);let agent=await agentResponse.json() as {id:string;lock_version:number};
  const assigned=await request.put(`${apiBase}/api/v1/agents/${agent.id}/tools`,{headers:auth(approver),data:{assignments:[{tool_name:"deployment_report",version_restriction:"active",assignment_action:"execute",enabled:true,risk_mode:"write",approval_required:false}]}});expect(assigned.status(),await assigned.text()).toBe(200);
  const published=await request.post(`${apiBase}/api/v1/agents/${agent.id}/publish`,{headers:{...auth(approver),"If-Match":String(agent.lock_version)},data:{change_note:"E2E governed release"}});expect(published.status(),await published.text()).toBe(200);agent=await published.json() as {id:string;lock_version:number};
  const enabled=await request.post(`${apiBase}/api/v1/agents/${agent.id}/enable`,{headers:{...auth(approver),"If-Match":String(agent.lock_version)},data:{change_note:"E2E enable",confirmed:true}});expect(enabled.status(),await enabled.text()).toBe(200);

  await setIdentity(page,approver);await page.goto("/copilot");
  const started=page.waitForResponse(response=>response.url().endsWith("/api/chat/start")&&response.request().method()==="POST");
  await page.getByLabel("Message Axiom Delivery AI").fill("Generate a deployment report for project_name=Atlas release_version=1.2 environment=staging status=succeeded");
  await page.getByLabel("Send message").click();
  const execution=await (await started).json() as {execution_id:string};
  const statusField=page.locator('form[aria-labelledby="required-information-title"] select');
  if(await statusField.waitFor({state:"visible",timeout:3000}).then(()=>true).catch(()=>false)){
    await statusField.selectOption("succeeded");
    await page.getByRole("button",{name:"Submit details"}).click();
  }
  await expect.poll(async()=>{
    const runtime=await request.get(`${apiBase}/api/runtime/${execution.execution_id}`,{headers:auth(approver)});
    return (await runtime.json() as {status:string}).status;
  },{timeout:30000}).toBe("COMPLETED");

  const datasetResponse=await request.post(`${apiBase}/api/evaluations/datasets`,{headers:auth(approver),data:{dataset_key:`completion-${suffix}`,name:"Completion security gate",version:1,status:"APPROVED",use_case:"copilot",cases:[{id:"authorized",checks:{schema:true,authorized:true}}]}});
  const dataset=await datasetResponse.json() as {id:string};
  const runResponse=await request.post(`${apiBase}/api/evaluations/runs`,{headers:auth(approver),data:{dataset_id:dataset.id,model_id:model.id,trace_ids:[execution.execution_id]}});expect(runResponse.status()).toBe(201);

  await page.goto(`/ai-operations/executions/${execution.execution_id}`);
  await expect(page.getByText(/"status": "SETTLED"/)).toBeVisible();
  await expect(page.getByText(/"input_tokens":/)).toBeVisible();
  await expect(page.getByText(/"evaluation_run_ids":/)).toBeVisible();
  await page.goto(`/ai-operations/budgets/${budget.id}`);await expect(page.getByText(/"settled_cost":/)).toBeVisible();
  await page.goto("/governance/audit");await expect(page.getByText("budget.reservation.settled",{exact:true}).first()).toBeVisible();
  await page.reload();await expect(page.getByText("budget.reservation.settled",{exact:true}).first()).toBeVisible();
});

test("hard limit blocks AI, override is separated, and deterministic pages survive",async({page,request},testInfo)=>{
  test.skip(testInfo.project.name!=="live-1440","Cross-module lifecycle runs once; responsive governance coverage runs separately.");
  const suffix=`${testInfo.project.name}-${Date.now()}`;const requester=token(`requester-${suffix}`);const approver=token(`override-approver-${suffix}`);const project=`project-${suffix}`;
  await activateModel(request,requester,approver,`override-${suffix}`);
  const budgetResponse=await request.post(`${apiBase}/api/ai-operations/budgets`,{headers:auth(requester),data:{scope_type:"PROJECT",scope_id:project,period:"MONTHLY",soft_limit:"0.005",hard_limit:"0.01",currency:"USD",alert_thresholds:[50,75,90,100],effective_from:new Date(Date.now()-60000).toISOString()}});expect(budgetResponse.status()).toBe(201);const budget=await budgetResponse.json() as {id:string};
  const conversationResponse=await request.post(`${apiBase}/conversations`,{headers:auth(requester),data:{title:`Budget ${suffix}`}});expect(conversationResponse.status()).toBe(200);const conversation=await conversationResponse.json() as {id:string};
  const blocked=await request.post(`${apiBase}/chat`,{headers:auth(requester),data:{message:"Critical AI analysis",conversation_id:conversation.id,metadata:{project_id:project,critical_ai_request:true}}});expect(blocked.status()).toBe(402);expect((await blocked.json()).detail.decision).toBe("REQUIRE_OVERRIDE_APPROVAL");
  const requested=await request.post(`${apiBase}/api/ai-operations/budgets/${budget.id}/overrides`,{headers:auth(requester),data:{requested_amount:"1.00",scope:{project_id:project},reason:"Critical release decision requires governed AI",business_impact:"Release decision",expires_at:new Date(Date.now()+3600000).toISOString(),single_use:true,uses_remaining:1,model_restrictions:["gpt-4.1-mini"],evidence:[]}});expect(requested.status()).toBe(201);const override=await requested.json() as {id:string};
  const selfApproval=await request.post(`${apiBase}/api/ai-operations/budget-overrides/${override.id}/approve`,{headers:auth(requester)});expect(selfApproval.status()).toBe(403);
  expect((await request.post(`${apiBase}/api/ai-operations/budget-overrides/${override.id}/approve`,{headers:auth(approver)})).status()).toBe(200);
  const allowed=await request.post(`${apiBase}/chat`,{headers:auth(requester),data:{message:"Critical AI analysis with approval",conversation_id:conversation.id,metadata:{project_id:project,critical_ai_request:true,budget_override_id:override.id}}});expect(allowed.status(),await allowed.text()).toBe(200);
  const duplicateUse=await request.post(`${apiBase}/chat`,{headers:auth(requester),data:{message:"Second use must fail",conversation_id:conversation.id,metadata:{project_id:project,critical_ai_request:true,budget_override_id:override.id}}});expect(duplicateUse.status()).toBe(402);
  expect((await request.get(`${apiBase}/api/ai-operations/budgets/${budget.id}`,{headers:auth(token(`other-${suffix}`,"other-tenant"))})).status()).toBe(404);

  await setIdentity(page,requester);await page.goto("/command-center");
  await expect(page.getByRole("heading",{name:/Good/})).toBeVisible();
  await page.goto("/sprints");await expect(page.getByRole("heading",{name:"Sprint Intelligence"})).toBeVisible();
});
