import { AlertCircle, CheckCircle, Clock, Loader2 } from "lucide-react";
import { activeRuntimeStatuses, formatRuntimeDuration, runtimeStatusPresentation } from "../../utils/runtimePresentation";

const statusStyle = {
  pending: "bg-stone-100 border-stone-300 text-stone-600",
  running: "bg-blue-50 border-blue-300 text-blue-700",
  completed: "bg-emerald-50 border-emerald-300 text-emerald-700",
  failed: "bg-red-50 border-red-300 text-red-700",
  cancelled: "bg-orange-50 border-orange-300 text-orange-700",
  timed_out: "bg-orange-50 border-orange-300 text-orange-700",
  unknown: "bg-stone-100 border-stone-300 text-stone-600",
};

function StepIcon({ status }) {
  if (status === "failed") return <AlertCircle className="h-5 w-5" />;
  if (status === "running") return <Loader2 className="h-5 w-5 animate-spin" />;
  if (status === "completed") return <CheckCircle className="h-5 w-5" />;
  return <Clock className="h-5 w-5" />;
}

export default function RuntimeExecutionCard({ metadata = {} }) {
  const steps = metadata.steps || [];
  const presentation=runtimeStatusPresentation[metadata.status]||{label:"Unknown",badge:"border-slate-400/30 bg-slate-400/10 text-slate-300"};

  return (
    <div className="border border-stone-300 border-t-4 border-t-[#a00028] bg-white p-6 text-stone-900 shadow-sm">
      <div className="mb-8 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center bg-[#a00028] text-xl text-white">🤖</div>
          <div>
            <h2 className="text-lg font-semibold text-stone-900">AI Runtime Orchestrator</h2>
            <p className="text-xs text-stone-500">Live execution trace</p>
          </div>
        </div>
        <span className={`rounded-full border px-4 py-2 text-xs font-medium ${presentation.badge}`}>● {presentation.label}</span>
      </div>

      {steps.length === 0 ? (
        <p className="border border-stone-200 bg-[#f4f1ed] p-4 text-sm text-stone-600">{activeRuntimeStatuses.has(metadata.status)?"Waiting for runtime events…":`Execution ${presentation.label.toLowerCase()}.`}</p>
      ) : (
        <div className="space-y-2">
          {steps.map((step, index) => (
            <div key={step.id || `${step.name}-${index}`} className="relative flex gap-4 pb-5">
              {index !== steps.length - 1 && <div className="absolute left-5 top-10 h-full w-px bg-stone-300" />}
              <div className={`relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border ${statusStyle[step.status] || statusStyle.pending}`}>
                <StepIcon status={step.status} />
              </div>
              <div className="flex-1 border border-stone-200 bg-[#faf8f5] px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium text-stone-900">{step.name}</p>
                  <span className="text-[10px] uppercase tracking-wide text-stone-500">{step.status}</span>
                </div>
                <p className="mt-1 text-sm text-stone-600">{step.description}</p>
                {(step.intent||step.extracted_parameters)&&<details className="mt-2 text-xs text-stone-600"><summary className="cursor-pointer font-medium text-[#a00028]">Structured decision</summary><div className="mt-2 space-y-1 border border-stone-200 bg-white p-2">{step.intent?.intent&&<p>Intent: {step.intent.intent}</p>}{Object.entries(step.extracted_parameters||{}).map(([key,item])=><p key={key}>{key.replaceAll("_"," ")}: {String(item.value)} <span className="text-stone-500">({item.source})</span></p>)}{step.missing_parameters?.length>0&&<p>Missing: {step.missing_parameters.join(", ")}</p>}{step.required_capabilities?.length>0&&<p>Capabilities: {step.required_capabilities.join(", ")}</p>}</div></details>}
                {step.timestamp && <p className="mt-2 text-[11px] text-slate-500">{new Date(step.timestamp).toLocaleTimeString()}</p>}
              </div>
            </div>
          ))}
        </div>
      )}

      {(metadata.agent || metadata.duration_ms != null || metadata.workflow_id) && (
        <div className="mt-4 grid gap-3 border-t border-stone-200 pt-4 text-sm sm:grid-cols-3">
          <div className="bg-[#f4f1ed] p-3"><p className="text-xs text-stone-500">Agent</p><p className="mt-1 truncate text-stone-800">{metadata.agent || (activeRuntimeStatuses.has(metadata.status)?"Resolving agent…":"Governed Runtime")}</p></div>
          <div className="bg-[#f4f1ed] p-3"><p className="text-xs text-stone-500">Duration</p><p className="mt-1 text-stone-800">{metadata.duration_ms==null&&activeRuntimeStatuses.has(metadata.status)?"In progress":formatRuntimeDuration(metadata.duration_ms)}</p></div>
          <div className="bg-[#f4f1ed] p-3"><p className="text-xs text-stone-500">Workflow ID</p><p className="mt-1 truncate text-stone-800" title={metadata.workflow_id}>{metadata.workflow_id}</p></div>
        </div>
      )}
      {metadata.agent && <div className="mt-4 border border-[#a00028]/25 bg-[#a00028]/5 p-4"><div className="flex items-start justify-between gap-3"><div><p className="text-xs uppercase tracking-wide text-[#a00028]">Selected agent</p><p className="mt-1 font-semibold text-stone-900">{metadata.agent}</p><p className="mt-1 text-xs text-stone-500">{metadata.provider || "Configured provider"} · {metadata.model || "Published model"}</p></div>{metadata.confidence!=null&&<span className="border border-emerald-300 bg-emerald-50 px-3 py-1 text-xs text-emerald-800">{Math.round(metadata.confidence*100)}% match</span>}</div>{metadata.candidates?.length>1&&<details className="mt-3 text-sm"><summary className="cursor-pointer text-stone-700">Other candidates ({metadata.candidates.length-1})</summary><div className="mt-2 space-y-2">{metadata.candidates.slice(1).map(candidate=><div key={candidate.agent_id} className="flex justify-between border border-stone-200 bg-white p-2"><span>{candidate.name}<small className="ml-2 text-stone-500">{candidate.reason}</small></span><span>{Math.round(candidate.confidence*100)}%</span></div>)}</div></details>}</div>}
      {["FAILED","CANCELLED","TIMED_OUT"].includes(metadata.status)&&<div className="mt-4 border border-rose-300 bg-rose-50 p-3 text-sm text-rose-900"><p>{metadata.error||(metadata.status==="TIMED_OUT"?"Execution timed out.":metadata.status==="CANCELLED"?"Execution cancelled.":"Execution failed.")}</p><p className="mt-1 text-xs text-rose-700">Support reference: {metadata.execution_id}</p></div>}
    </div>
  );
}
