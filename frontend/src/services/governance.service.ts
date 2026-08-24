import api from "./api";

export type Page<T=Record<string,unknown>>={items:T[];total:number;page?:number;page_size?:number};
export type Policy={id:string;name:string;description:string;category:string;version:number;status:string;priority:number;conditions:Record<string,unknown>;effect:Record<string,unknown>;reason_codes:string[];created_by:string;approved_by?:string|null;review_date?:string|null};
export type GovernanceOverview={summary:Record<string,number|null>;attention:Array<Record<string,unknown>>;human_oversight:Record<string,number|null>;sources:string[]};
export type OperationsOverview={summary:Record<string,string|number|null>;charts:Record<string,unknown[]>;attention:Array<Record<string,unknown>>;sources:string[]};

export const governanceApi={
  overview:()=>api.get<GovernanceOverview>("/api/governance/overview").then(r=>r.data),
  policies:()=>api.get<Page<Policy>>("/api/governance/policies").then(r=>r.data),
  policy:(id:string)=>api.get<Policy>(`/api/governance/policies/${id}`).then(r=>r.data),
  simulate:(id:string,scenario:Record<string,unknown>)=>api.post(`/api/governance/policies/${id}/simulate`,{scenario}).then(r=>r.data),
  permissions:()=>api.get<Page>("/api/governance/permissions").then(r=>r.data),
  roles:()=>api.get<Page>("/api/governance/roles").then(r=>r.data),
  accessReviews:()=>api.get<Page>("/api/governance/access-reviews").then(r=>r.data),
  audit:()=>api.get<Page>("/api/audit/events").then(r=>r.data),
  auditEvent:(id:string)=>api.get(`/api/audit/events/${id}`).then(r=>r.data),
  retention:()=>api.get<Page>("/api/governance/retention").then(r=>r.data),
  operations:()=>api.get<OperationsOverview>("/api/ai-operations/overview").then(r=>r.data),
  executions:()=>api.get<Page>("/api/ai-operations/executions").then(r=>r.data),
  execution:(id:string)=>api.get(`/api/ai-operations/executions/${id}`).then(r=>r.data),
  evaluations:()=>api.get<Page>("/api/evaluations/runs").then(r=>r.data),
  evaluation:(id:string)=>api.get(`/api/evaluations/runs/${id}`).then(r=>r.data),
  costs:()=>api.get<Record<string,unknown>>("/api/ai-operations/costs").then(r=>r.data),
  budgets:()=>api.get<Page>("/api/ai-operations/budgets").then(r=>r.data),
  budget:(id:string)=>api.get(`/api/ai-operations/budgets/${id}`).then(r=>r.data),
  incidents:()=>api.get<Page>("/api/ai-operations/incidents").then(r=>r.data),
  models:()=>api.get<Page>("/api/models").then(r=>r.data),
  model:(id:string)=>api.get(`/api/models/${id}`).then(r=>r.data),
};
