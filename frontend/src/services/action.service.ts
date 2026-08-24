import api from "./api";
import {mockActionById,mockActions} from "../pages/actions/data/mockActions";
import {isDeliveryMockMode} from "../config/deliveryDataMode";

export type EvidenceReference = {
  id: string;
  title: string;
  sourceSystem: string;
  sourceUrl?: string | null;
  capturedAt: string;
};

export type Approval = {
  id: string;
  proposedActionId: string;
  actionVersion: number;
  requesterId: string;
  assignedApproverId?: string | null;
  riskLevel: string;
  status: string;
  safeActionSummary: Record<string, unknown>;
  separationOfDuties: boolean;
  createdAt: string;
  expiresAt: string;
  decisionReason?: string | null;
  capabilities?: {
    canView:boolean;
    canApprove:boolean;
    canReject:boolean;
    canRequestChanges:boolean;
    canDelegate:boolean;
    denialReasonCode?:string|null;
  };
  decisions: Array<{id:string;decision:string;actorId:string;comment?:string;createdAt:string}>;
  action?: ProposedAction;
};

export type ProposedAction = {
  id: string;
  actionType: string;
  title: string;
  description: string;
  origin: string;
  requesterId: string;
  targetEntityType?: string | null;
  targetEntityId?: string | null;
  targetSystem: string;
  payload: Record<string, unknown>;
  status: string;
  riskLevel: string;
  policyVersion: number;
  expiresAt?: string | null;
  failure?: {code:string;message:string}|null;
  version: number;
  createdAt: string;
  updatedAt: string;
  evidence: EvidenceReference[];
  approvals: Approval[];
  executions: Array<{id:string;status:string;adapter:string;attemptNumber:number;traceId:string;failureMessage?:string}>;
  auditTrail: Array<{id:number;action:string;actorId:string;occurredAt:string;correlationId?:string}>;
  availableTransitions: string[];
};

type Page<T> = {items:T[];total:number;page:number};

export const getActions = (params?:Record<string,string>) =>
  isDeliveryMockMode()?Promise.resolve((()=>{const status=params?.status?.split(",").filter(Boolean),search=params?.search?.toLowerCase();const items=mockActions.filter(item=>(!status?.length||status.includes(item.status))&&(!search||`${item.title} ${item.description}`.toLowerCase().includes(search)));return {items,total:items.length,page:1};})()):api.get<Page<ProposedAction>|ProposedAction[]>("/api/actions", {params}).then(response=>{
    const data=response.data;
    return Array.isArray(data)?{items:data,total:data.length,page:1}:{...data,items:data.items??[]};
  });
export const getAction = (id:string) =>
  isDeliveryMockMode()?Promise.resolve(mockActionById(id)):api.get<ProposedAction>(`/api/actions/${id}`).then(response=>response.data);
export const createAction = (payload:unknown) =>
  api.post<ProposedAction>("/api/actions",payload).then(response=>response.data);
export const updateAction = (id:string,payload:unknown) =>
  api.patch<ProposedAction>(`/api/actions/${id}`,payload).then(response=>response.data);
export const submitAction = (id:string,assignedApproverId?:string) =>
  api.post<Approval>(`/api/actions/${id}/submit`,{assigned_approver_id:assignedApproverId||null}).then(response=>response.data);
export const executeAction = (id:string,idempotencyKey:string) =>
  api.post(`/api/actions/${id}/execute`,{idempotency_key:idempotencyKey}).then(response=>response.data);
export const verifyAction = (id:string,comment:string) =>
  api.post(`/api/actions/${id}/verify`,{comment}).then(response=>response.data);
export const cancelAction = (id:string,comment:string) =>
  api.post(`/api/actions/${id}/cancel`,{comment}).then(response=>response.data);

export const getApprovals = (params?:Record<string,string>) =>
  api.get<Page<Approval>|Approval[]>("/api/approvals",{params}).then(response=>{
    const data=response.data;
    return Array.isArray(data)?{items:data,total:data.length,page:1}:{...data,items:data.items??[]};
  });
export const getApproval = (id:string) =>
  api.get<Approval>(`/api/approvals/${id}`).then(response=>response.data);
export const getApprovalSummary = () => api.get("/api/approvals/summary").then(response=>response.data);
export const getSubmittedApprovals = () => getApprovalsFrom("/api/approvals/submitted");
export const getApprovalHistory = () => getApprovalsFrom("/api/approvals/history");
const getApprovalsFrom = (url:string) => api.get<Page<Approval>|Approval[]>(url).then(response=>{
  const data=response.data;
  return Array.isArray(data)?{items:data,total:data.length,page:1}:{...data,items:data.items??[]};
});
export const getApprovalEvidence = (id:string) => api.get(`/api/approvals/${id}/evidence`).then(response=>response.data);
export const getApprovalImpact = (id:string) => api.get(`/api/approvals/${id}/impact`).then(response=>response.data);
export const getApprovalExecution = (id:string) => api.get(`/api/approvals/${id}/execution`).then(response=>response.data);
export const getApprovalActivity = (id:string) => api.get(`/api/approvals/${id}/activity`).then(response=>response.data);
export const decideApproval = (id:string,decision:"approve"|"reject"|"request-changes",comment:string) =>
  api.post<Approval>(`/api/approvals/${id}/${decision}`,{comment}).then(response=>response.data);
export const delegateApproval = (id:string,delegateTo:string,comment:string) =>
  api.post<Approval>(`/api/approvals/${id}/delegate`,{delegate_to:delegateTo,comment}).then(response=>response.data);
export const getPolicies = () => api.get("/api/action-policies").then(response=>response.data);
