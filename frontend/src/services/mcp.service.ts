import api from "./api";

export type MCPServerInput = {
  display_name: string; slug?: string; description?: string; environment?: string;
  server_url: string; transport: "streamable_http" | "sse";
  auth_type: "none" | "api_key" | "oauth2" | "jwt" | "service_account";
  secret_reference?: string; auth_config?: Record<string, unknown>;
  requested_scopes?: string[]; policy?: Record<string, unknown>; enabled?: boolean;
};
export const listMCPServers=(params={})=>api.get("/api/v1/mcp/servers",{params}).then(r=>r.data);
export const getMCPServer=(id:string)=>api.get(`/api/v1/mcp/servers/${id}`).then(r=>r.data);
export const createMCPServer=(input:MCPServerInput)=>api.post("/api/v1/mcp/servers",input).then(r=>r.data);
export const updateMCPServer=(id:string,input:Partial<MCPServerInput>)=>api.patch(`/api/v1/mcp/servers/${id}`,input).then(r=>r.data);
export const testMCPServer=(id:string)=>api.post(`/api/v1/mcp/servers/${id}/test`).then(r=>r.data);
export const syncMCPServer=(id:string)=>api.post(`/api/v1/mcp/servers/${id}/sync`).then(r=>r.data);
export const listMCPCapabilities=(id:string)=>api.get(`/api/v1/mcp/servers/${id}/capabilities`).then(r=>r.data);
export const updateMCPCapability=(sid:string,cid:string,input:Record<string,unknown>)=>api.patch(`/api/v1/mcp/servers/${sid}/capabilities/${cid}`,input).then(r=>r.data);
export const executeMCPTool=(sid:string,cid:string,input:Record<string,unknown>)=>api.post(`/api/v1/mcp/servers/${sid}/tools/${cid}/execute`,{input}).then(r=>r.data);
export const readMCPResource=(sid:string,uri:string)=>api.post(`/api/v1/mcp/servers/${sid}/resources/read`,{uri}).then(r=>r.data);
export const getMCPPrompt=(sid:string,name:string,args:Record<string,unknown>)=>api.post(`/api/v1/mcp/servers/${sid}/prompts/${encodeURIComponent(name)}`,{arguments:args}).then(r=>r.data);
export const listMCPSyncRuns=(id:string)=>api.get(`/api/v1/mcp/servers/${id}/sync-runs`).then(r=>r.data);
export const listMCPExecutions=(id:string)=>api.get(`/api/v1/mcp/servers/${id}/executions`).then(r=>r.data);
