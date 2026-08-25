import api from "./api";

export type CopilotPage<T>={items:T[];total:number;page:number;pageSize:number};
export type SavedInsight={id:string;title:string;summary:string;insightType:string;conversationId?:string;executionId?:string;deliveryContext:Record<string,unknown>;confidence:string;evidenceSnapshots:Array<Record<string,unknown>>;evidenceFreshness?:string;ownerId:string;tags:string[];reviewDate?:string;status:string;version:number;createdAt:string;updatedAt:string};
export type PromptTemplate={id:string;templateKey:string;name:string;description:string;category:string;promptBody:string;requiredContextTypes:string[];expectedResponseType:string;evidenceRequirement:string;mayProposeAction:boolean;ownerId:string;version:number;status:string;favorite:boolean;createdAt:string;updatedAt:string};

export const listSavedInsights=(params?:Record<string,string|number|boolean>,signal?:AbortSignal)=>api.get<CopilotPage<SavedInsight>>("/api/copilot/saved-insights",{params,signal}).then(response=>response.data);
export const getSavedInsight=(id:string,signal?:AbortSignal)=>api.get<SavedInsight>(`/api/copilot/saved-insights/${id}`,{signal}).then(response=>response.data);
export const createSavedInsight=(payload:unknown)=>api.post<SavedInsight>("/api/copilot/saved-insights",payload).then(response=>response.data);
export const updateSavedInsight=(id:string,payload:unknown)=>api.patch<SavedInsight>(`/api/copilot/saved-insights/${id}`,payload).then(response=>response.data);
export const archiveSavedInsight=(id:string,version:number)=>api.post<SavedInsight>(`/api/copilot/saved-insights/${id}/archive`,null,{params:{version}}).then(response=>response.data);
export const listPromptTemplates=(params?:Record<string,string|number|boolean>,signal?:AbortSignal)=>api.get<CopilotPage<PromptTemplate>>("/api/copilot/prompt-templates",{params,signal}).then(response=>response.data);
export const getPromptTemplate=(id:string,signal?:AbortSignal)=>api.get<PromptTemplate>(`/api/copilot/prompt-templates/${id}`,{signal}).then(response=>response.data);
export const createPromptTemplate=(payload:unknown)=>api.post<PromptTemplate>("/api/copilot/prompt-templates",payload).then(response=>response.data);
export const updatePromptTemplate=(id:string,payload:unknown)=>api.patch<PromptTemplate>(`/api/copilot/prompt-templates/${id}`,payload).then(response=>response.data);
export const transitionPromptTemplate=(id:string,transition:string)=>api.post<PromptTemplate>(`/api/copilot/prompt-templates/${id}/lifecycle/${transition}`).then(response=>response.data);
export const favoritePromptTemplate=(id:string)=>api.post(`/api/copilot/prompt-templates/${id}/favorite`).then(response=>response.data);
export const unfavoritePromptTemplate=(id:string)=>api.delete(`/api/copilot/prompt-templates/${id}/favorite`);
