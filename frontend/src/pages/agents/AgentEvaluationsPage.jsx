import { ArrowLeft, CheckCircle2, FlaskConical, TriangleAlert } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getAgent, getAgentEvaluations } from "../../services/agentService";

export default function AgentEvaluationsPage() {
  const { agentId } = useParams();
  const agent = useQuery({ queryKey: ["agent", agentId], queryFn: () => getAgent(agentId), retry: false });
  const runs = useQuery({ queryKey: ["agent", agentId, "evaluations"], queryFn: () => getAgentEvaluations(agentId), retry: false });
  if (agent.isLoading || runs.isLoading) return <main className="p-8" aria-live="polite">Loading agent evaluations…</main>;
  if (agent.error || runs.error) return <main className="p-8" role="alert"><h1 className="text-2xl font-bold">Evaluations unavailable</h1><p className="mt-2 text-stone-600">The agent does not exist or you do not have access.</p></main>;
  const latest = runs.data.items[0];
  const score = latest ? Object.values(latest.scores || {}).filter((value) => typeof value === "number").reduce((sum, value, _, values) => sum + value / Math.max(values.length, 1), 0) : null;
  return <main className="min-h-full bg-[#faf8f5] p-4 text-stone-900 md:p-8">
    <Link to={`/agents/${agentId}/overview`} className="inline-flex items-center gap-2 text-sm font-semibold text-stone-600"><ArrowLeft size={16} />{agent.data.name}</Link>
    <header className="mt-5"><p className="text-xs font-bold uppercase tracking-[0.18em] text-[#a00028]">Agent management</p><h1 className="mt-2 font-display text-4xl font-bold">Evaluations</h1><p className="mt-2 text-stone-600">Controlled evaluation runs for agent version {agent.data.current_version}.</p></header>
    <section className="mt-6 grid gap-3 sm:grid-cols-3"><Metric label="Latest score" value={score == null ? "No data" : `${score.toFixed(1)}%`} icon={FlaskConical} /><Metric label="Latest result" value={latest?.status || "Not evaluated"} icon={latest?.status === "PASSED" ? CheckCircle2 : TriangleAlert} /><Metric label="Evaluation runs" value={runs.data.total} icon={FlaskConical} /></section>
    <section className="mt-6 overflow-hidden rounded-2xl border border-stone-300 bg-white shadow-sm"><div className="border-b border-stone-200 p-5"><h2 className="text-xl font-bold">Evaluation history</h2><p className="mt-1 text-sm text-stone-500">Runs use approved datasets and governed models through the shared evaluation framework.</p></div>{runs.data.items.length ? <div className="overflow-x-auto"><table className="min-w-[760px] w-full text-left text-sm"><thead className="bg-stone-50 text-xs uppercase text-stone-500"><tr><th className="p-3">Status</th><th className="p-3">Agent version</th><th className="p-3">Dataset</th><th className="p-3">Model</th><th className="p-3">Failures</th><th className="p-3">Started</th></tr></thead><tbody>{runs.data.items.map((run) => <tr key={run.id} className="border-t border-stone-200"><td className="p-3 font-semibold">{run.status}</td><td className="p-3">v{run.agent_version}</td><td className="p-3">{run.dataset_id} · v{run.dataset_version}</td><td className="p-3">{run.model_id}</td><td className="p-3">{run.failures?.length || 0}</td><td className="p-3">{new Date(run.started_at).toLocaleString()}</td></tr>)}</tbody></table></div> : <p className="p-8 text-center text-stone-500">No controlled evaluation has been run for this agent.</p>}</section>
  </main>;
}

function Metric({ label, value, icon: Icon }) { return <article className="rounded-2xl border border-stone-300 bg-white p-4 shadow-sm"><div className="flex justify-between text-stone-500"><p className="text-xs font-bold uppercase tracking-wide">{label}</p><Icon size={18} className="text-[#a00028]" /></div><p className="mt-3 text-2xl font-bold">{value}</p></article>; }
