import {useEffect,useRef,useState} from "react";
import {CircleHelp} from "lucide-react";
import DynamicFieldRenderer from "./DynamicFieldRenderer";

export default function RequiredInformationCard({request,onSubmit,onCancel}){
  const [values,setValues]=useState(request?.known_values||{});const [submitting,setSubmitting]=useState(false);const [errors,setErrors]=useState({});const [submissionError,setSubmissionError]=useState("");const headingRef=useRef(null);
  useEffect(()=>headingRef.current?.focus(),[request?.continuation_id]);
  if(!request)return null;
  const feedback=request.validation_feedback||{};const serverErrors={};for(const name of feedback.invalid_fields||[])serverErrors[name]="Enter a valid value for this field.";for(const name of feedback.unresolved_fields||[])serverErrors[name]="This value is still required.";const visibleErrors={...serverErrors,...errors};const visibleSubmissionError=submissionError||(feedback.warnings||[]).join(" ");
  async function submit(e){e.preventDefault();const next={};for(const field of request.fields||[])if(field.required&&(values[field.name]===undefined||values[field.name]===""||values[field.name]===null||(Array.isArray(values[field.name])&&!values[field.name].length)))next[field.name]=`${field.label} is required.`;setErrors(next);if(Object.keys(next).length)return;setSubmitting(true);setSubmissionError("");try{await onSubmit(values)}catch(error){setSubmissionError(error instanceof Error?error.message:"Unable to submit runtime details.")}finally{setSubmitting(false)}}
  return <form noValidate className="rounded-2xl border border-amber-400/20 bg-[#0b1930] p-5" onSubmit={submit} aria-labelledby="required-information-title">
    <div className="flex items-center gap-3"><span className="rounded-xl bg-amber-500/20 p-2 text-amber-300"><CircleHelp size={18}/></span><div><h3 id="required-information-title" ref={headingRef} tabIndex={-1} className="font-semibold">{request.title||"Additional Information Required"}</h3><p className="text-xs text-slate-400">{request.description||"Execution is paused and will resume with the same runtime ID."}</p></div></div>
    {Object.keys(visibleErrors).length>0&&<p role="alert" className="mt-3 rounded-lg bg-rose-500/10 p-3 text-sm text-rose-200">Complete the marked required fields.</p>}
    {visibleSubmissionError&&<p role="alert" className="mt-3 rounded-lg bg-rose-500/10 p-3 text-sm text-rose-200">{visibleSubmissionError}</p>}
    <div className="mt-4 grid gap-4 md:grid-cols-2">{(request.fields||[]).map(field=><label className="text-sm text-slate-300" key={field.name}>{field.label}{field.required&&<span className="text-rose-400"> *</span>}<DynamicFieldRenderer field={field} value={values[field.name]} invalid={Boolean(visibleErrors[field.name])} onChange={value=>{setValues(current=>({...current,[field.name]:value}));setErrors(current=>({...current,[field.name]:undefined}))}}/>{visibleErrors[field.name]&&<span className="mt-1 block text-xs text-rose-300">{visibleErrors[field.name]}</span>}</label>)}</div>
    <div className="mt-5 flex justify-end gap-2"><button type="button" onClick={onCancel} className="rounded-lg border border-white/10 px-4 py-2 text-sm">Cancel execution</button><button disabled={submitting} className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium">{submitting?"Submitting…":"Submit details"}</button></div>
  </form>
}
