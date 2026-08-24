import { useState } from "react";
import { Sparkles } from "lucide-react";

export default function DetectedRAIDReview({candidate,onAccept,onDismiss,busy}) {
  const [editing,setEditing]=useState(false);
  if(!candidate)return <aside className="border border-dashed border-stone-300 bg-white p-5" aria-label="Detected RAID candidates"><h2 className="font-display text-xl font-bold">Detected candidates</h2><p className="mt-2 text-sm text-stone-500">No evidence-backed candidates require review.</p></aside>;
  const evidence=Array.isArray(candidate.evidence)?candidate.evidence:[];
  const possibleDuplicates=Array.isArray(candidate.possibleDuplicates)?candidate.possibleDuplicates:[];
  const limitations=Array.isArray(candidate.limitations)?candidate.limitations:[];
  return <aside className="border-t-4 border-[#e0301e] bg-[#202020] p-5 text-white" aria-labelledby="detected-raid-title">
    <div className="flex items-center gap-2 text-[#ffb600]"><Sparkles size={18}/><h2 id="detected-raid-title" className="font-semibold">Detected RAID candidate</h2></div>
    <p className="mt-4 font-display text-lg leading-7">{candidate.title}</p>
    <p className="mt-2 text-sm leading-6 text-stone-300">{candidate.description}</p>
    <dl className="mt-5 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-stone-400">Type</dt><dd className="font-semibold">{candidate.candidateType}</dd></div><div><dt className="text-stone-400">Confidence</dt><dd className="font-semibold text-[#ffb600]">{Math.round(candidate.confidence*100)}% — evidence-based</dd></div><div><dt className="text-stone-400">Evidence</dt><dd>{evidence.length} authorized source{evidence.length===1?"":"s"}</dd></div><div><dt className="text-stone-400">Duplicates</dt><dd>{possibleDuplicates.length} possible</dd></div></dl>
    {limitations.length>0&&<p className="mt-4 text-xs text-stone-400">Limitation: {limitations.join("; ")}</p>}
    {editing?<form className="mt-5 grid gap-3 border border-white/20 p-4" onSubmit={event=>{event.preventDefault();onAccept(candidate,Object.fromEntries(new FormData(event.currentTarget)))}}>
      <label className="text-xs font-semibold">Reviewed title<input required name="name" defaultValue={candidate.title} className="mt-1 w-full border border-white/30 bg-white p-2 text-sm text-stone-950"/></label>
      <label className="text-xs font-semibold">Reviewed description<textarea required name="description" defaultValue={candidate.description} className="mt-1 min-h-24 w-full border border-white/30 bg-white p-2 text-sm text-stone-950"/></label>
      <label className="text-xs font-semibold">Owner<input required name="owner_id" defaultValue={candidate.suggestedOwner||""} className="mt-1 w-full border border-white/30 bg-white p-2 text-sm text-stone-950"/></label>
      <label className="text-xs font-semibold">Due date<input required type="date" name="due_date" defaultValue={candidate.suggestedDueDate||""} className="mt-1 w-full border border-white/30 bg-white p-2 text-sm text-stone-950"/></label>
      {candidate.candidateType==="RISK"&&<div className="grid grid-cols-2 gap-2"><label className="text-xs font-semibold">Probability<select name="probability" defaultValue={candidate.suggestedProbability||"POSSIBLE"} className="mt-1 w-full bg-white p-2 text-stone-950">{["RARE","UNLIKELY","POSSIBLE","LIKELY","ALMOST_CERTAIN"].map(value=><option key={value}>{value}</option>)}</select></label><label className="text-xs font-semibold">Impact<select name="impact" defaultValue={candidate.suggestedImpact||"MODERATE"} className="mt-1 w-full bg-white p-2 text-stone-950">{["LOW","MINOR","MODERATE","HIGH","CRITICAL"].map(value=><option key={value}>{value}</option>)}</select></label></div>}
      <div className="grid grid-cols-2 gap-2"><button type="button" onClick={()=>setEditing(false)} className="border border-white/30 px-3 py-2 text-sm font-semibold">Cancel</button><button disabled={busy} className="bg-[#e0301e] px-3 py-2 text-sm font-semibold disabled:opacity-50">Accept edited candidate</button></div>
    </form>:<div className="mt-6 grid gap-2"><button type="button" disabled={busy} onClick={()=>setEditing(true)} className="bg-[#e0301e] px-4 py-2.5 text-sm font-semibold disabled:opacity-50">Review and edit</button><button type="button" disabled={busy} onClick={()=>onDismiss(candidate)} className="border border-white/30 px-4 py-2.5 text-sm font-semibold disabled:opacity-50">Dismiss with reason</button></div>}
    <p className="mt-4 text-xs text-stone-400">Human review is required. No external record is created.</p>
  </aside>;
}
