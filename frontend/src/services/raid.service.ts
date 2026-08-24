import api from "./api";
import { getMockRAIDDetail, getMockRAIDItems, mockRAIDCandidate, mockRAIDHeatmap, mockRAIDHygiene, mockRAIDSummary } from "../pages/raid/data/mockRAID";
import {isDeliveryMockMode} from "../config/deliveryDataMode";

export type RAIDType = "RISK" | "ASSUMPTION" | "ISSUE" | "DEPENDENCY" | "DECISION" | "ACTION";

export interface RAIDItem {
  id: string; reference: string; name: string; description: string; itemType: RAIDType; status: string;
  priority?: string; ownerId?: string; projectId: string; sprintId?: string; releaseId?: string; milestoneId?: string;
  probability?: string; impact?: string; exposureScore?: number; exposureBand?: string; residualExposureScore?: number;
  residualExposureBand?: string; attentionScore?: number; attentionReasons: string[]; dueDate?: string; reviewDate?: string;
  identifiedAt: string; ageDays: number; evidenceCount: number; version: number; mitigationPlan?: string; resolutionPlan?: string;
  severity?: string; validationOwnerId?: string; validationDueDate?: string; decisionOwnerId?: string; criticalPath?: boolean;
}
export interface RAIDListResponse { items: RAIDItem[]; page: number; pageSize: number; total: number; pages: number; traceId: string; generatedAt: string; source: "persisted" | "mock"; }
export interface RAIDSummary { criticalRisks: number; openIssues: number; atRiskDependencies: number; pendingDecisions: number; overdueActions: number; unvalidatedAssumptions: number; generatedAt: string; }
export interface HeatmapCell { probability: string; impact: string; score: number; band: string; count: number; itemIds: string[]; }
export interface RAIDCandidate { id: string; candidateType: RAIDType; title: string; description: string; confidence: number; evidence: Array<{id:string;title:string;sourceType:string}>; affectedEntities: Array<{type:string;id:string}>; suggestedOwner?: string; suggestedDueDate?: string; suggestedProbability?: string; suggestedImpact?: string; possibleDuplicates: Array<{id:string;reference:string;title:string;confidence:number;reasons:string[]}>; limitations: string[]; status: string; traceId: string; version: number; }
export interface RAIDDetail { item: RAIDItem; evidence: Array<{id:string;title:string;summary?:string;sourceType:string;sourceSystem:string;sourceUrl?:string;capturedAt:string}>; relationships: Array<{id:string;entityType:string;entityId:string;relationshipType:string}>; recommendations: Array<{id:string;title:string;explanation:string;priority:string;confidence:number;status:string}>; proposals: Array<{id:string;actionType:string;content:string;status:string;approvalRequired:boolean;createdAt:string}>; reviews: Array<{id:string;note:string;reviewedBy:string;reviewedAt:string;nextReviewDate?:string}>; history: Array<{id:string;eventType:string;previousStatus?:string;newStatus?:string;note?:string;actorId:string;changedAt:string}>; traceId: string; source: "persisted" | "mock"; externalWrites: false; }
export interface RAIDFilters { type?: RAIDType; status?: string; exposure_band?: string; probability?: string; impact?: string; project_id?: string; owner_id?: string; search?: string; overdue?: boolean; stale?: boolean; unowned?: boolean; critical_path?: boolean; page?: number; page_size?: number; sort?: string; direction?: "asc"|"desc"; }

const useMockData = isDeliveryMockMode;
export async function getRAIDItems(filters: RAIDFilters = {}, signal?: AbortSignal): Promise<RAIDListResponse> { if(useMockData()) return getMockRAIDItems(filters); const {data}=await api.get<RAIDListResponse>("/api/raid",{params:filters,signal}); return data; }
export async function getRAIDSummary(signal?: AbortSignal): Promise<RAIDSummary> { if(useMockData()) return mockRAIDSummary; const {data}=await api.get<RAIDSummary>("/api/raid/summary",{signal}); return data; }
export async function getRAIDHeatmap(signal?: AbortSignal): Promise<{cells:HeatmapCell[];totalRisks:number;generatedAt:string}> { if(useMockData()) return {cells:mockRAIDHeatmap,totalRisks:mockRAIDHeatmap.reduce((sum,cell)=>sum+cell.count,0),generatedAt:mockRAIDSummary.generatedAt}; const {data}=await api.get("/api/raid/heatmap",{signal}); return data; }
export async function getRAIDHygiene(signal?: AbortSignal): Promise<{items:Array<Record<string,string>>;total:number;generatedAt:string}> { if(useMockData()) return {items:mockRAIDHygiene,total:mockRAIDHygiene.length,generatedAt:mockRAIDSummary.generatedAt}; const {data}=await api.get("/api/raid/hygiene",{signal}); return data; }
export async function getRAIDCandidates(signal?: AbortSignal): Promise<{items:RAIDCandidate[]}> { if(useMockData()) return {items:[mockRAIDCandidate]}; const {data}=await api.get("/api/raid/candidates",{signal}); return data; }
export async function getRAIDDetail(id:string,signal?:AbortSignal): Promise<RAIDDetail> { if(useMockData()){const detail=getMockRAIDDetail(id);if(!detail)throw new Error("RAID item not found");return detail;} const {data}=await api.get<RAIDDetail>(`/api/raid/${encodeURIComponent(id)}`,{signal}); return data; }
export async function createRAIDItem(payload:Record<string,unknown>) { const {data}=await api.post("/api/raid",payload); return data as {item:RAIDItem;possibleDuplicates:unknown[];traceId:string}; }
export async function updateRAIDItem(id:string,payload:Record<string,unknown>) { const {data}=await api.patch(`/api/raid/${encodeURIComponent(id)}`,payload); return data as {item:RAIDItem;traceId:string}; }
export async function transitionRAIDItem(id:string,expectedVersion:number,status:string,note?:string) { const {data}=await api.post(`/api/raid/${encodeURIComponent(id)}/transition`,{expected_version:expectedVersion,status,note}); return data as {item:RAIDItem;traceId:string}; }
export async function reviewRAIDItem(id:string,expectedVersion:number,note:string,nextReviewDate?:string) { const {data}=await api.post(`/api/raid/${encodeURIComponent(id)}/review`,{expected_version:expectedVersion,note,next_review_date:nextReviewDate}); return data; }
export async function acceptRAIDCandidate(id:string,payload:Record<string,unknown>) { const {data}=await api.post(`/api/raid/detected/${encodeURIComponent(id)}/accept`,payload); return data as {item:RAIDItem;candidate:RAIDCandidate;humanReviewed:true}; }
export async function dismissRAIDCandidate(id:string,reason:string) { const {data}=await api.post(`/api/raid/detected/${encodeURIComponent(id)}/dismiss`,{reason}); return data; }
export async function createRAIDProposal(id:string,payload:Record<string,unknown>) { const {data}=await api.post(`/api/raid/${encodeURIComponent(id)}/proposals`,payload); return data as {proposal:{id:string;status:string};traceId:string;externalWrites:false;approvalRequired:true}; }
