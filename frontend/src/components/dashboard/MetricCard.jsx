export default function MetricCard({ title, value, trend, icon: Icon }) {
  return <article className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-xl backdrop-blur-xl">
    <div className="flex items-start justify-between"><span className="text-sm text-slate-300">{title}</span><div className="rounded-xl bg-blue-500/15 p-2 text-blue-300"><Icon size={19}/></div></div>
    <p className="mt-4 text-3xl font-semibold text-white">{value}</p><p className="mt-2 text-xs text-emerald-400">↑ {trend}% from last month</p>
  </article>;
}
