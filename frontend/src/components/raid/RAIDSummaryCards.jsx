import { AlertTriangle, CheckSquare, GitBranch, HelpCircle, Lightbulb, ShieldAlert } from "lucide-react";

const cards = [
  ["criticalRisks", "Critical risks", ShieldAlert, "RISK"],
  ["openIssues", "Open issues", AlertTriangle, "ISSUE"],
  ["atRiskDependencies", "At-risk dependencies", GitBranch, "DEPENDENCY"],
  ["pendingDecisions", "Pending decisions", HelpCircle, "DECISION"],
  ["overdueActions", "Overdue actions", CheckSquare, "ACTION"],
  ["unvalidatedAssumptions", "Unvalidated assumptions", Lightbulb, "ASSUMPTION"],
];

export default function RAIDSummaryCards({ summary, loading, onSelect }) {
  return <section aria-labelledby="raid-summary-title" className="mt-6"><h2 id="raid-summary-title" className="sr-only">RAID summary</h2><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">{cards.map(([key,label,Icon,type])=><button key={key} type="button" onClick={()=>onSelect(type)} aria-label={`${label}: ${loading?"loading":summary?.[key]??0}. Filter register.`} className="group border border-stone-300 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-[#e0301e] focus:outline-none focus:ring-2 focus:ring-[#e0301e] motion-reduce:transform-none"><span className="flex items-center justify-between text-stone-500"><Icon size={18} aria-hidden="true"/><span className="text-xs uppercase tracking-wider">View</span></span><strong className="mt-5 block min-h-9 font-display text-3xl tabular-nums text-stone-950">{loading?<span className="inline-block h-8 w-12 animate-pulse bg-stone-200 motion-reduce:animate-none" aria-hidden="true"/>:summary?.[key]??0}</strong><span className="mt-1 block text-sm font-semibold text-stone-700 group-hover:text-[#a00028]">{label}</span></button>)}</div></section>;
}
