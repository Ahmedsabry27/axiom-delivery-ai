import { runtimeStatuses, type RuntimeEvent, type RuntimeExecutionViewModel, type RuntimeSnapshot, type RuntimeStatus } from "../types/runtime";

const validStatuses = new Set<string>(runtimeStatuses);
const terminalStatuses = new Set<RuntimeStatus>(["COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"]);
export const isRuntimeStatus = (value: unknown): value is RuntimeStatus => typeof value === "string" && validStatuses.has(value);
export const isTerminalRuntimeStatus = (value: RuntimeStatus) => terminalStatuses.has(value);

export const initialRuntimeState: RuntimeExecutionViewModel = {
  status:"PENDING", stateVersion:0, lastSequence:0, candidates:[], stepsById:{}, stepOrder:[], steps:[],
  toolsById:{}, toolOrder:[], tools:[], actionsById:{}, actionOrder:[], actions:[], plan:[],
  requiredInput:null, approval:null, logs:[], metrics:{}, sources:[], error:null,
};

type RuntimeAction =
  | {type:"started"; execution:Partial<RuntimeSnapshot> & {execution_id:string;workflow_id:string}}
  | {type:"event"; event:RuntimeEvent}
  | {type:"hydrate"; runtime:RuntimeSnapshot}
  | {type:"reset"};

const identity = (event:RuntimeEvent) => String(event.step_id || event.component_id || event.tool_execution_id || event.action_execution_id || `${event.component_type || event.type}:${event.name || "event"}`);
const mergeProjection = (byId:Record<string,RuntimeEvent>, order:string[], event:RuntimeEvent) => {
  const key=identity(event); const exists=Boolean(byId[key]);
  return {byId:{...byId,[key]:{...(byId[key]||{}),...event}},order:exists?order:[...order,key]};
};
const materialize=(byId:Record<string,RuntimeEvent>,order:string[])=>order.map(key=>byId[key]).filter((item):item is RuntimeEvent=>item!==undefined);
const settleUnknown=(items:Record<string,RuntimeEvent>)=>Object.fromEntries(Object.entries(items).map(([key,item])=>[key,item.status==="running"?{...item,status:"unknown" as const,description:item.description||"Terminal child status is unavailable"}:item]));
const errorFrom=(value:{error?:string;error_code?:string;execution_id?:string;metadata?:Record<string,unknown>}):RuntimeExecutionViewModel["error"] => value.error ? {message:value.error,code:value.error_code,supportReference:value.execution_id,retryable:Boolean(value.metadata?.retryable)} : null;

export function runtimeReducer(state:RuntimeExecutionViewModel, action:RuntimeAction):RuntimeExecutionViewModel {
  if(action.type==="reset") return initialRuntimeState;
  if(action.type==="started") {
    const runtime=action.execution;
    return {...initialRuntimeState,executionId:runtime.execution_id,workflowId:runtime.workflow_id,status:isRuntimeStatus(runtime.status)?runtime.status:"PENDING",stateVersion:runtime.state_version||0,lastSequence:runtime.last_sequence||0};
  }
  if(action.type==="hydrate") {
    const runtime=action.runtime;
    if(state.executionId&&state.executionId!==runtime.execution_id) return state;
    const version=runtime.state_version||0;
    if(version<state.stateVersion) return state;
    if(!isRuntimeStatus(runtime.status)) { console.error("Unknown authoritative runtime status",{execution_id:runtime.execution_id,state_version:version,status:runtime.status}); return state; }
    const selectedAgent=runtime.agent?{...(state.selectedAgent||{}),name:runtime.agent,id:runtime.agent_id,provider:runtime.provider,model:runtime.model,selectionMode:runtime.metadata?.selection_mode}:state.selectedAgent;
    const next={...state,executionId:runtime.execution_id,workflowId:runtime.workflow_id,status:runtime.status,stateVersion:version,lastSequence:Math.max(state.lastSequence,runtime.last_sequence||0),startedAt:runtime.started_at,finishedAt:runtime.finished_at,durationMs:runtime.duration_ms,selectedAgent,
      requiredInput:runtime.status==="WAITING_FOR_INPUT"?(runtime.continuation as RuntimeEvent)||null:null,
      approval:runtime.status==="WAITING_FOR_APPROVAL"?(runtime.continuation as RuntimeEvent)||null:null,
      metrics:{...state.metrics,provider:runtime.provider,model:runtime.model,token_usage:runtime.token_usage,estimated_cost:runtime.estimated_cost,actual_cost:runtime.actual_cost,duration_ms:runtime.duration_ms},
      finalResponse:runtime.status==="COMPLETED"?runtime.result_message:undefined,error:runtime.status==="COMPLETED"?null:errorFrom(runtime)};
    if(isTerminalRuntimeStatus(runtime.status)){next.toolsById=settleUnknown(next.toolsById);next.tools=materialize(next.toolsById,next.toolOrder);next.actionsById=settleUnknown(next.actionsById);next.actions=materialize(next.actionsById,next.actionOrder);}
    return next;
  }
  const event=action.event;
  if(state.executionId&&event.execution_id!==state.executionId) return state;
  const sequence=event.sequence||0;
  if(sequence>0&&sequence<=state.lastSequence) return state;
  const next={...state,executionId:event.execution_id||state.executionId,workflowId:event.workflow_id||state.workflowId,lastSequence:Math.max(state.lastSequence,sequence)};
  const eventVersion=event.state_version||0;
  if(event.aggregate_status!==undefined) {
    if(!isRuntimeStatus(event.aggregate_status)) console.error("Unknown runtime event aggregate status",{execution_id:event.execution_id,sequence,event_type:event.type,aggregate_status:event.aggregate_status});
    else if(eventVersion>=state.stateVersion) {next.status=event.aggregate_status;next.stateVersion=Math.max(state.stateVersion,eventVersion);}
  }
  if(event.type==="required_input") next.requiredInput={...event,kind:"input"};
  else if(event.type==="approval_required") next.approval={...event,kind:"approval"};
  else if(event.type.startsWith("tool_")){const merged=mergeProjection(state.toolsById,state.toolOrder,event);next.toolsById=merged.byId;next.toolOrder=merged.order;next.tools=materialize(merged.byId,merged.order);}
  else if(event.type.startsWith("action_")){const merged=mergeProjection(state.actionsById,state.actionOrder,event);next.actionsById=merged.byId;next.actionOrder=merged.order;next.actions=materialize(merged.byId,merged.order);}
  else if(event.type==="log") next.logs=[...state.logs,event];
  else if(event.type==="metric") next.metrics={...state.metrics,...(event.metadata||{})};
  else if(event.type==="knowledge_retrieval_completed"&&event.source) next.sources=[...state.sources,event.source];
  else if(event.type!=="heartbeat"&&event.type!=="error"){const merged=mergeProjection(state.stepsById,state.stepOrder,event);next.stepsById=merged.byId;next.stepOrder=merged.order;next.steps=materialize(merged.byId,merged.order);}
  if(event.plan) next.plan=(event.plan as {steps?:unknown[]}).steps||[];
  if(event.agent) next.selectedAgent={...state.selectedAgent,name:event.agent,id:event.agent_id,provider:event.provider,model:event.model,confidence:event.confidence,selectionMode:event.selection_mode,reason:event.selection_reason,capabilities:event.capabilities,tools:event.assigned_tools,knowledgeSourceCount:event.knowledge_source_count};
  if(event.candidates) next.candidates=event.candidates;
  if(event.provider||event.model) next.metrics={...next.metrics,provider:event.provider||next.metrics.provider,model:event.model||next.metrics.model};
  if(next.status!=="WAITING_FOR_INPUT") next.requiredInput=null;
  if(next.status!=="WAITING_FOR_APPROVAL") next.approval=null;
  if(isTerminalRuntimeStatus(next.status)){
    next.requiredInput=null;next.approval=null;next.finalResponse=next.status==="COMPLETED"?event.message||state.finalResponse:undefined;
    next.error=next.status==="COMPLETED"?null:(event.error?{message:event.error,code:event.error_code,supportReference:event.execution_id}:state.error);
    next.toolsById=settleUnknown(next.toolsById);next.tools=materialize(next.toolsById,next.toolOrder);
    next.actionsById=settleUnknown(next.actionsById);next.actions=materialize(next.actionsById,next.actionOrder);
  }
  return next;
}
