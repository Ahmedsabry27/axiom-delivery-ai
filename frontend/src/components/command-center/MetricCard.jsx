import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import StatusBadge from "./StatusBadge";
export default function MetricCard({ metric, icon: Icon }) {
  const improving = metric.change >= 0;
  const directionIsGood = ["Open Risks"].includes(metric.label) ? !improving : improving;
  const TrendIcon = improving ? ArrowUpRight : ArrowDownRight;
  return <a href={metric.route||"#"} title={metric.definition} className="block border border-stone-300 border-t-4 border-t-[#e0301e] bg-white p-5 text-left transition hover:border-t-[#a00028] focus:outline-none focus:ring-2 focus:ring-[#e0301e]">
    <div className="flex items-start justify-between"><div className="bg-[#f4f1ed] p-2.5 text-[#a00028]"><Icon className="h-5 w-5" aria-hidden="true" /></div><StatusBadge>{metric.status}</StatusBadge></div>
    <p className="mt-5 text-sm font-medium text-stone-500">{metric.label}</p>
    <div className="mt-1 flex items-end justify-between gap-3"><strong className="font-display tabular-nums text-4xl tracking-tight text-[#202020]">{metric.state==="missing"?"—":`${metric.value}${metric.unit||""}`}</strong><span className="text-sm font-medium text-stone-600">{metric.state==="partial"?"Partial data":metric.detail}</span></div>
    <p className={`mt-4 flex items-center gap-1 text-xs font-medium ${directionIsGood ? "text-emerald-700" : "text-amber-700"}`}><TrendIcon className="h-3.5 w-3.5" aria-hidden="true" />{Math.abs(metric.change)} {metric.changeLabel}</p>
  </a>;
}
