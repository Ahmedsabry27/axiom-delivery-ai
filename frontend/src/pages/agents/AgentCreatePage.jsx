import { ArrowLeft } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import AgentCreateWizard from "../../components/agents/AgentCreateWizard";

export default function AgentCreatePage() {
  const navigate = useNavigate();
  return (
    <main className="min-h-full bg-[#faf8f5] p-4 text-stone-900 md:p-8">
      <Link to="/agents" className="inline-flex items-center gap-2 text-sm font-semibold text-stone-600 hover:text-[#a00028]">
        <ArrowLeft size={16} /> Agents
      </Link>
      <header className="mt-5">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#a00028]">Agent management</p>
        <h1 className="mt-2 font-display text-4xl font-bold">Create agent</h1>
        <p className="mt-2 text-stone-600">Build a governed draft using approved models, tools, and knowledge sources.</p>
      </header>
      <AgentCreateWizard onCancel={() => navigate("/agents")} onSaved={(agent) => navigate(`/agents/${agent.id}/overview`)} />
    </main>
  );
}
