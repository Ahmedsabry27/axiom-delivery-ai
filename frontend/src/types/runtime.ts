export const runtimeStatuses = ["PENDING", "RUNNING", "WAITING_FOR_INPUT", "WAITING_FOR_APPROVAL", "COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"] as const;
export type RuntimeStatus = typeof runtimeStatuses[number];
export type RuntimeStepStatus = "pending" | "running" | "completed" | "failed" | "waiting" | "cancelled" | "timed_out" | "unknown";
export type RuntimeEventType = string;

export interface AgentCandidate { agent_id: string; name: string; slug: string; capabilities: string[]; provider: string; model?: string; confidence: number; reason: string }
export interface RequiredField { name: string; label: string; type: string; required?: boolean; options?: Array<string | {label:string;value:string}>; description?: string }
export interface RuntimeError { code?: string; message: string; retryable?: boolean; supportReference?: string; component?: string; operation?: string }
export interface RuntimeEvent {
  type: RuntimeEventType; execution_id: string; workflow_id: string; event_id?: string; sequence?: number; state_version?: number; step_id?: string; name?: string; description?: string;
  status?: RuntimeStepStatus; timestamp?: string; agent?: string; agent_id?: string; provider?: string; model?: string;
  confidence?: number; candidates?: AgentCandidate[]; duration_ms?: number; message?: string; error?: string; error_code?: string; final?: boolean;
  aggregate_status?: RuntimeStatus; component_type?: string; component_id?: string; component_status?: string;
  continuation_id?: string; fields?: RequiredField[]; metadata?: Record<string, unknown>; [key: string]: unknown;
}
export interface RuntimeSnapshot {
  execution_id: string; workflow_id: string; status: RuntimeStatus; state_version?: number; last_sequence?: number;
  started_at?: string; finished_at?: string; duration_ms?: number; agent?: string; agent_id?: string; provider?: string; model?: string;
  result_message?: string; error?: string; error_code?: string; continuation?: Record<string, unknown> | null;
  token_usage?: Record<string, unknown>; estimated_cost?: number; actual_cost?: number; metadata?: Record<string, unknown>;
}

export interface RuntimeExecutionViewModel {
  executionId?: string; workflowId?: string; status: RuntimeStatus; stateVersion: number; lastSequence: number;
  startedAt?: string; finishedAt?: string; durationMs?: number; selectedAgent?: Record<string, unknown>;
  candidates: AgentCandidate[]; stepsById: Record<string, RuntimeEvent>; stepOrder: string[]; steps: RuntimeEvent[];
  toolsById: Record<string, RuntimeEvent>; toolOrder: string[]; tools: RuntimeEvent[];
  actionsById: Record<string, RuntimeEvent>; actionOrder: string[]; actions: RuntimeEvent[];
  plan: unknown[]; requiredInput?: RuntimeEvent | null; approval?: RuntimeEvent | null; logs: RuntimeEvent[];
  metrics: Record<string, unknown>; sources: unknown[]; finalResponse?: string; error?: RuntimeError | null;
}
