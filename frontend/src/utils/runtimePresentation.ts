import type { RuntimeStatus } from "../types/runtime";

export const activeRuntimeStatuses = new Set<RuntimeStatus>(["PENDING","RUNNING","WAITING_FOR_INPUT","WAITING_FOR_APPROVAL"]);
export const terminalRuntimeStatuses = new Set<RuntimeStatus>(["COMPLETED","FAILED","CANCELLED","TIMED_OUT"]);

export function formatRuntimeDuration(durationMs?:number):string {
  if(durationMs==null)return "—";
  if(durationMs<1000)return `${Math.round(durationMs)} ms`;
  if(durationMs<60000)return `${(durationMs/1000).toFixed(1)} s`;
  const minutes=Math.floor(durationMs/60000);const seconds=Math.round((durationMs%60000)/1000);
  return `${minutes}m ${seconds}s`;
}

export function runtimeFailureMessage(runtime:{status?:RuntimeStatus;error?:{code?:string;message?:string}|null}):string {
  if(runtime.error?.code==="BUDGET_ENFORCEMENT_BLOCKED"&&runtime.error?.message==="MODEL_NOT_APPROVED") {
    return "Chat is unavailable because the selected AI model has not been approved for this workspace. Ask a model administrator to activate an approved Copilot model.";
  }
  return runtime.error?.message||
    (runtime.status==="TIMED_OUT"?"Execution timed out.":runtime.status==="CANCELLED"?"Execution cancelled.":"Execution failed.");
}

export const runtimeStatusPresentation:Record<RuntimeStatus,{label:string;badge:string;dot:string}>={
  PENDING:{label:"Pending",badge:"border-slate-400/30 bg-slate-400/10 text-slate-300",dot:"bg-slate-400"},
  RUNNING:{label:"Running",badge:"border-blue-400/30 bg-blue-400/10 text-blue-300",dot:"bg-blue-400 animate-pulse"},
  WAITING_FOR_INPUT:{label:"Waiting for input",badge:"border-amber-400/30 bg-amber-400/10 text-amber-300",dot:"bg-amber-400"},
  WAITING_FOR_APPROVAL:{label:"Waiting for approval",badge:"border-amber-400/30 bg-amber-400/10 text-amber-300",dot:"bg-amber-400"},
  COMPLETED:{label:"Completed",badge:"border-emerald-400/30 bg-emerald-400/10 text-emerald-300",dot:"bg-emerald-400"},
  FAILED:{label:"Failed",badge:"border-rose-400/30 bg-rose-400/10 text-rose-300",dot:"bg-rose-400"},
  CANCELLED:{label:"Cancelled",badge:"border-slate-400/30 bg-slate-400/10 text-slate-300",dot:"bg-slate-400"},
  TIMED_OUT:{label:"Timed out",badge:"border-orange-400/30 bg-orange-400/10 text-orange-300",dot:"bg-orange-400"},
};
