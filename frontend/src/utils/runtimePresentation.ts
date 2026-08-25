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
  PENDING:{label:"Pending",badge:"border-stone-300 bg-stone-100 text-stone-700",dot:"bg-stone-500"},
  RUNNING:{label:"Running",badge:"border-blue-300 bg-blue-50 text-blue-800",dot:"bg-blue-600 animate-pulse"},
  WAITING_FOR_INPUT:{label:"Waiting for input",badge:"border-amber-300 bg-amber-50 text-amber-900",dot:"bg-amber-600"},
  WAITING_FOR_APPROVAL:{label:"Waiting for approval",badge:"border-amber-300 bg-amber-50 text-amber-900",dot:"bg-amber-600"},
  COMPLETED:{label:"Completed",badge:"border-emerald-300 bg-emerald-50 text-emerald-800",dot:"bg-emerald-600"},
  FAILED:{label:"Failed",badge:"border-rose-300 bg-rose-50 text-rose-800",dot:"bg-rose-600"},
  CANCELLED:{label:"Cancelled",badge:"border-stone-300 bg-stone-100 text-stone-700",dot:"bg-stone-500"},
  TIMED_OUT:{label:"Timed out",badge:"border-orange-300 bg-orange-50 text-orange-800",dot:"bg-orange-600"},
};
