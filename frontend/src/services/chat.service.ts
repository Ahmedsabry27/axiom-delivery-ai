import api from "./api";

export interface StartExecutionRequest {
  message: string;
  conversation_id: string;
  agent_id?: string | null;
  provider?: "openai" | "bedrock" | null;
  model?: string | null;
  workspace_id?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface StartExecutionResponse {
  execution_id: string;
  workflow_id: string;
  status: string;
  agent_version?: number;
}

export async function sendMessage(payload: StartExecutionRequest): Promise<StartExecutionResponse> {
  return startExecution(payload);
}

export async function startExecution(
  payload: StartExecutionRequest,
): Promise<StartExecutionResponse> {
  const response = await api.post<StartExecutionResponse>("/api/chat/start", payload);
  return response.data;
}
