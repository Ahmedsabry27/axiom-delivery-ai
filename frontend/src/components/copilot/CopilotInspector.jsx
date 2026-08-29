import {useMemo,useState} from "react";
import {FileCheck2,Layers3,Radio} from "lucide-react";
import {deliveryContexts} from "./deliveryContexts";
import {runtimeActivity} from "../../utils/runtimeActivity";

const tabs=["Context","Evidence","Activity"];
const array=value=>Array.isArray(value)?value:[];
export default function CopilotInspector({contextId,messages,runtime,onContextChange}){
 const [tab,setTab]=useState("Context");
 const context=deliveryContexts.find(item=>item.id===contextId);
 const evidence=useMemo(()=>messages.flatMap(message=>array(message.metadata?.structured_response?.evidence)).filter((item,index,all)=>all.findIndex(candidate=>candidate.id===item.id)===index),[messages]);
 const activity=runtimeActivity([...array(runtime.steps),...array(runtime.tools),...array(runtime.actions)],runtime.status);
 return <aside className="hidden w-[360px] shrink-0 border-l border-stone-300 bg-white text-stone-900 xl:flex xl:flex-col" aria-label="Copilot context and evidence inspector"><div className="flex border-b border-stone-300">{tabs.map(item=><button key={item} onClick={()=>setTab(item)} className={`flex-1 border-b-4 px-3 py-3 text-xs font-semibold ${tab===item?"border-[#a00028] text-[#a00028]":"border-transparent text-stone-500"}`}>{item}</button>)}</div><div className="flex-1 overflow-y-auto p-4">
 {tab==="Context"&&<section><h2 className="font-display flex items-center gap-2 text-xl font-bold"><Layers3 size={18}/>Active context</h2>{context?<div className="mt-4 border border-stone-300 p-4"><strong>{context.label||context.name}</strong><p className="mt-1 text-xs uppercase text-stone-500">{context.type||"Delivery context"}</p><button onClick={()=>onContextChange("")} className="mt-4 border border-stone-400 px-3 py-2 text-xs font-semibold">Clear context</button></div>:<p className="mt-4 border-l-4 border-amber-500 bg-amber-50 p-3 text-sm">No delivery context selected. Axiom will not infer one.</p>}</section>}
 {tab==="Evidence"&&<section><h2 className="font-display flex items-center gap-2 text-xl font-bold"><FileCheck2 size={18}/>Authorized evidence</h2>{evidence.length?<div className="mt-4 space-y-3">{evidence.map(item=><article id={`copilot-evidence-${item.id}`} key={item.id} className="border border-stone-300 p-3"><strong className="text-sm">{item.title}</strong><p className="mt-1 text-xs text-stone-600">{item.summary||"Excerpt restricted or unavailable."}</p><dl className="mt-2 text-xs text-stone-500"><dt>Source</dt><dd>{item.sourceType||item.source||"Authorized source"}</dd><dt className="mt-1">Freshness</dt><dd>{item.freshness||item.capturedAt||"Not reported"}</dd></dl></article>)}</div>:<p className="mt-4 text-sm text-stone-500">No authorized evidence has been attached to this conversation.</p>}</section>}
 {tab==="Activity"&&<section><h2 className="font-display flex items-center gap-2 text-xl font-bold"><Radio size={18}/>Safe activity</h2><div className="mt-4 space-y-2">{activity.length?activity.map(item=><div key={item.id} className="border-l-2 border-stone-300 bg-[#faf8f5] px-3 py-2"><strong className="text-sm">{item.label}</strong><p className="mt-0.5 text-xs capitalize text-stone-500">{item.state}{item.durationMs!=null?` · ${Math.round(item.durationMs)} ms`:""}</p></div>):<p className="text-sm text-stone-500">No runtime activity recorded yet.</p>}</div><p className="mt-4 text-xs text-stone-500">Private reasoning, raw prompts, credentials and restricted evidence are never shown.</p></section>}
 </div></aside>;
}
