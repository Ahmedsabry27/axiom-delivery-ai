import { AlertTriangle, CalendarClock, CheckCircle2, ClipboardCheck, MessageSquareText, RefreshCw, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { PageSkeleton, ErrorState } from "../../components/command-center/CommandCenterStates";
import StatusBadge from "../../components/command-center/StatusBadge";
import { useMyDay } from "../../hooks/useMyDay";
import useAuth from "../../hooks/useAuth";

const icons={
  Attention:AlertTriangle,
  Meeting:CalendarClock,
  Approval:ClipboardCheck,
  Action:CheckCircle2,
  Risk:AlertTriangle,
  Assumption:ClipboardCheck,
  Issue:AlertTriangle,
  Dependency:CalendarClock,
  Decision:ClipboardCheck,
  "RAID Candidate":Sparkles,
  "Dependency Candidate":Sparkles,
};
export default function MyDayPage(){
  const query=useMyDay(); const {user}=useAuth();
  if(query.isLoading)return <PageSkeleton/>; if(query.error)return <ErrorState onRetry={query.refetch}/>; const data=query.data;
  return <main className="min-h-full bg-[#faf8f5] p-5 text-[#202020] md:p-8"><header className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[.18em] text-[#a00028]">Personal delivery workspace</p><h1 className="font-display mt-2 text-4xl font-bold">My Day, {user?.givenName||user?.name?.split(" ")[0]||"there"}</h1><p className="mt-2 text-stone-600">Your decisions, commitments and briefings in one place.</p></div><button onClick={()=>query.refetch()} className="inline-flex items-center gap-2 border border-stone-300 bg-white px-4 py-2.5 text-sm font-semibold"><RefreshCw className={`h-4 w-4 ${query.isFetching?"animate-spin":""}`}/>Refresh</button></header>
  <div className="mt-7 grid gap-6 xl:grid-cols-[2fr_1fr]"><section className="border border-stone-300 bg-white" aria-labelledby="today-title"><div className="flex items-center justify-between border-b border-stone-200 p-5"><div><h2 id="today-title" className="font-display text-xl font-bold">Today’s focus</h2><p className="text-sm text-stone-500">Prioritised by urgency, delivery impact and your ownership</p></div><div className="text-right"><strong className="text-3xl text-[#a00028]">{data.focusScore}</strong><p className="text-xs text-stone-500">focus score</p></div></div><div className="divide-y divide-stone-100">{data.items.map(item=>{const Icon=icons[item.kind]||AlertTriangle;return <article key={item.id} className="flex gap-4 p-5"><div className="bg-[#f4f1ed] p-2.5 text-[#a00028]"><Icon className="h-5 w-5"/></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{item.kind} · {item.time||`Due ${item.dueDate}`}</p><h3 className="mt-1 font-semibold">{item.route?<Link to={item.route} className="text-[#a00028] underline underline-offset-4">{item.title}</Link>:item.title}</h3></div><StatusBadge>{item.priority}</StatusBadge></div><p className="mt-2 text-sm leading-6 text-stone-600">{item.summary}</p><p className="mt-2 text-xs font-medium text-stone-500">{item.context}</p></div></article>})}</div></section>
  <aside className="space-y-6"><section className="border border-stone-300 bg-white p-5"><div className="flex items-center gap-3"><Sparkles className="h-5 w-5 text-[#a00028]"/><h2 className="font-display text-xl font-bold">Briefings</h2></div>{data.briefings.map(b=><article key={b.id} className="mt-5"><h3 className="font-semibold">{b.title}</h3><p className="mt-2 text-sm leading-6 text-stone-600">{b.summary}</p><p className="mt-3 text-xs text-stone-500">Based on {b.evidenceCount} evidence points</p></article>)}</section><Link to="/copilot" className="flex items-center justify-between bg-[#a00028] p-5 text-white"><span><strong className="block">Ask Axiom</strong><span className="mt-1 block text-sm text-white/80">Explore today’s delivery context</span></span><MessageSquareText className="h-6 w-6"/></Link></aside></div></main>;
}
