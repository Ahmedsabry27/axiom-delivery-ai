/* eslint-disable @typescript-eslint/no-explicit-any */
import api from "./api";
export type ChecklistItem={id:string;itemKey:string;section:string;label:string;description:string;required:boolean;weight:number;evidenceRequired:boolean;responsibleRole?:string;status:string;comment?:string;evidenceRefs:Array<Record<string,unknown>>;completedBy?:string;completedAt?:string;applicabilityReason?:string;source:string;version:number};
export type Ceremony={id:string;meetingId?:string;templateId:string;templateVersion:number;templateSnapshot:Record<string,unknown>;title:string;ceremonyType:string;status:string;teamId?:string;programmeId?:string;projectId?:string;scheduledStart?:string;facilitatorId?:string;purpose:string;agenda:string[];scores:Record<string,any>;analysisFindings:any[];themes:any[];version:number;updatedAt:string};
export type Template={id:string;familyKey:string;name:string;ceremonyType:string;description:string;purpose:string;requiredRoles:string[];recommendedTimeboxMinutes?:number;items:any[];requiredEvidence:string[];expectedDecisions:string[];expectedOutputs:string[];scoringConfig:Record<string,unknown>;templateVersion:number;effectiveDate?:string;ownerId?:string;status:string;version:number};
export type Lesson={id:string;ceremonyId?:string;meetingId?:string;title:string;category:string;sentiment:string;status:string;context:string;expectedOutcome:string;actualOutcome:string;rootCause:string;contributingFactors:string[];recommendation:string;evidenceRefs:any[];affectedEntities:any[];applicability:any[];ownerId?:string;reviewerId?:string;reviewDate?:string;publishedAt?:string;version:number;updatedAt:string;adoptions:any[]};
export const listCeremonies=async()=>((await api.get("/api/ceremonies")).data as {items:Ceremony[]}).items;
export const getCeremony=async(id:string)=>(await api.get<Ceremony>(`/api/ceremonies/${id}`)).data;
export const listTemplates=async()=>((await api.get("/api/ceremonies/templates")).data as {items:Template[]}).items;
export const getTemplate=async(id:string)=>(await api.get<Template>(`/api/ceremonies/templates/${id}`)).data;
export const getChecklist=async(id:string)=>(await api.get<{items:ChecklistItem[];scores:any}>(`/api/ceremonies/${id}/checklist`)).data;
export const updateChecklist=async(id:string,item:ChecklistItem,status:string,extra:Record<string,unknown>={})=>(await api.patch(`/api/ceremonies/${id}/checklist/${item.itemKey}`,{expected_version:item.version,status,...extra})).data;
export const getCeremonySection=async(id:string,section:string)=>(await api.get(`/api/ceremonies/${id}/${section}`)).data;
export const listLessons=async()=>((await api.get("/api/lessons")).data as {items:Lesson[]}).items;
export const getLesson=async(id:string)=>(await api.get<Lesson>(`/api/lessons/${id}`)).data;
