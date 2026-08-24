import fs from "node:fs";
import { expect, test } from "@playwright/test";

type E2EState = { token:string; cross_tenant_token:string; dependency_id:string; evidence_id:string; project_id:string; work_item_id:string; sprint_id:string; milestone_id:string; release_id:string; actor:string };
const statePath=process.env.E2E_STATE_PATH;
if(!statePath)throw new Error("E2E_STATE_PATH is required");
const state=JSON.parse(fs.readFileSync(statePath,"utf8")) as E2EState;
const apiBase=process.env.VITE_API_URL||"http://127.0.0.1:8000";

test.beforeEach(async({page})=>{await page.addInitScript(token=>window.sessionStorage.setItem("e2e_access_token",token),state.token)});

test("persisted dependency journey remains read-only and human reviewed",async({page,request})=>{
  const headers={Authorization:`Bearer ${state.token}`};
  await page.goto("/dependencies");
  await expect(page.getByRole("heading",{name:"Dependency Intelligence"})).toBeVisible();
  await expect(page.getByRole("button",{name:/Critical dependencies/})).toContainText(/[1-9]/);
  await page.getByRole("tab",{name:"Graph"}).click();
  await expect(page.getByRole("heading",{name:"Accessible relationship view"})).toBeVisible();
  await page.getByRole("button",{name:"Zoom in"}).click();
  await page.getByRole("button",{name:"Fit dependency graph to view"}).click();
  await page.getByRole("button",{name:"Select D-018"}).click();
  await page.getByRole("button",{name:"Expand upstream"}).click();
  await expect(page.getByRole("status")).toContainText("upstream node");
  await page.getByRole("button",{name:"Expand downstream"}).click();
  await expect(page.getByRole("status")).toContainText("downstream node");
  await page.getByRole("button",{name:"Highlight critical path"}).click();
  await expect(page.getByRole("status")).toContainText("critical path highlighted");
  await page.getByRole("button",{name:"D-018",exact:true}).click();
  const detail=page.getByRole("dialog",{name:"D-018"});
  await expect(detail).toContainText("Customer API delivery");
  await expect(detail).toContainText(state.actor);
  await expect(detail).toContainText("Identity provider delivery delayed");

  const impactResponse=page.waitForResponse(response=>response.url().endsWith("/api/dependencies/graph/scenarios")&&response.request().method()==="POST");
  await detail.getByRole("button",{name:"Run 5-day impact"}).click();
  const impact=await impactResponse;
  expect(impact.status()).toBe(200);
  const simulation=await impact.json();
  expect(simulation.authoritativeRecordsChanged).toBe(false);
  expect(simulation.scenarioResult.affectedSprints).toContain(state.sprint_id);
  expect(simulation.scenarioResult.affectedMilestones).toContain(state.milestone_id);
  expect(simulation.scenarioResult.affectedReleases).toContain(state.release_id);
  await detail.getByRole("button",{name:"Close dependency details"}).click();
  await expect(page.getByText(/authoritative records changed: false/)).toBeVisible();
  await page.getByRole("button",{name:"Save",exact:true}).click();
  await expect(page.getByText(/Scenario saved to the durable audit trail/)).toBeVisible();

  const copilot=await request.post(`${apiBase}/api/dependencies/copilot`,{headers,data:{question:"What happens if D-018 slips five days?",dependency_id:state.dependency_id,slip_days:5}});
  expect(copilot.status()).toBe(200);
  const answer=await copilot.json();
  expect(answer.responseType).toBe("DEPENDENCY_INTELLIGENCE");
  expect(answer.externalWrites).toBe(false);

  await page.goto(`/dependencies/${state.dependency_id}`);
  await page.getByLabel("Draft escalation").fill("Draft a synthetic provider escalation for human approval.");
  const proposed=page.waitForResponse(response=>response.url().endsWith(`/api/dependencies/${state.dependency_id}/proposals`)&&response.request().method()==="POST");
  await page.getByRole("button",{name:"Save as proposed"}).click();
  expect((await proposed).status()).toBe(201);
  await expect(page.getByText(/Nothing was executed externally/)).toBeVisible();
  await page.reload();
  const persisted=page.getByRole("dialog",{name:"D-018"});
  await expect(persisted).toContainText("Draft a synthetic provider escalation for human approval.");
  await expect(persisted).toContainText("PROPOSED INTERVENTION CREATED");
  const persistedScenario=await request.get(`${apiBase}/api/dependencies/${state.dependency_id}`,{headers});
  expect((await persistedScenario.json()).scenarios.length).toBeGreaterThan(0);
});

test("cycle and cross-tenant dependency operations are rejected",async({request})=>{
  const headers={Authorization:`Bearer ${state.token}`};
  const cycle=await request.post(`${apiBase}/api/dependencies`,{headers,data:{reference:"D-CYCLE",name:"Rejected cycle",description:"Synthetic cycle candidate.",project_id:state.project_id,dependency_type:"TECHNICAL",relationship_type:"DEPENDS_ON",provider:{entity_type:"RELEASE",entity_id:state.release_id},consumer:{entity_type:"EXTERNAL_PARTY",entity_id:"identity-provider"},external:true,status:"IDENTIFIED"}});
  expect(cycle.status()).toBe(409);
  expect((await cycle.json()).detail).toContain("cycle");

  const foreign={Authorization:`Bearer ${state.cross_tenant_token}`};
  expect((await request.get(`${apiBase}/api/dependencies/${state.dependency_id}`,{headers:foreign})).status()).toBe(404);
  const graph=await request.get(`${apiBase}/api/dependencies/graph`,{headers:foreign});
  expect(graph.status()).toBe(200);
  expect((await graph.json()).edgeCount).toBe(0);
  expect((await request.post(`${apiBase}/api/dependencies/graph/scenarios`,{headers:foreign,data:{dependency_id:state.dependency_id,slip_days:5,save:true}})).status()).toBe(404);
  expect((await request.post(`${apiBase}/api/dependencies/${state.dependency_id}/proposals`,{headers:foreign,data:{action_type:"DRAFT_ESCALATION",content:"Forbidden cross-tenant draft",status:"PROPOSED",evidence_ids:[state.evidence_id]}})).status()).toBe(404);
});
