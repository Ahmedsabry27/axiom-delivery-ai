import { useState } from "react";
import { BrainCircuit, FileSearch, ShieldCheck } from "lucide-react";

import api from "../../services/api";

export default function SprintCopilotPanel({ sprint }) {
  const [insight, setInsight] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [auditEvents, setAuditEvents] = useState([]);
  const [selectedEvidence, setSelectedEvidence] = useState(null);

  async function generateInsight() {
    setStatus("loading");
    setError("");
    try {
      const conversation = await api.post("/conversations", {
        title: `${sprint.name} readiness review`,
      });
      const response = await api.post("/api/delivery/copilot/sprint-insight", {
        conversation_id: conversation.data.id,
        sprint_id: sprint.id,
        message: "Will we meet the sprint goal, what is the primary risk, and what intervention should we consider?",
      });
      setInsight(response.data);
      setStatus("ready");
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Unable to generate sprint insight.");
      setStatus("error");
    }
  }

  async function saveDraft() {
    setStatus("saving");
    setError("");
    const recommendation = insight.recommendations?.[0];
    const dependency = insight.dependencies?.[0];
    const blockedItem = insight.blockedWork?.[0];
    try {
      await api.post("/api/delivery/proposed-actions", {
        conversation_id: insight.conversationId,
        message_id: insight.assistantMessageId,
        response_id: insight.id,
        sprint_id: sprint.id,
        work_item_id: blockedItem?.id || null,
        dependency_id: dependency?.id || null,
        recommendation_id: recommendation?.id || null,
        trace_id: insight.traceId,
        action_type: "SPRINT_INTERVENTION",
        content: recommendation?.explanation || `Review and resolve ${insight.primaryRisk}.`,
        target: sprint.name,
        evidence_ids: insight.evidence.map((item) => item.id),
        status: "DRAFT",
      });
      const audit = await api.get("/api/delivery/audit-events", {
        params: { trace_id: insight.traceId },
      });
      setAuditEvents(audit.data.items);
      setStatus("saved");
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Unable to save the proposed intervention.");
      setStatus("error");
    }
  }

  return (
    <section aria-labelledby="sprint-copilot-title" className="mt-6 border border-stone-300 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[.15em] text-[#a00028]">Evidence-backed intervention</p>
          <h2 id="sprint-copilot-title" className="font-display mt-1 text-2xl font-bold">Axiom sprint assessment</h2>
          <p className="mt-2 max-w-2xl text-sm text-stone-600">Generate a persisted assessment from authorized sprint records. Any intervention remains a draft for human review.</p>
        </div>
        <button type="button" onClick={generateInsight} disabled={status === "loading" || status === "saving"} className="inline-flex items-center gap-2 bg-[#a00028] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
          <BrainCircuit className="h-4 w-4" />{status === "loading" ? "Assessing…" : "Ask Axiom about this sprint"}
        </button>
      </div>

      {error && <p role="alert" className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {insight && (
        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div>
            <p className="border-l-4 border-[#e65b19] bg-[#faf8f5] p-4 text-sm font-semibold text-stone-800">
              Goal confidence {insight.goalConfidence}%. Forecast {insight.forecast.completed_points} points. Primary risk: {insight.primaryRisk}.
            </p>
            <h3 className="mt-5 flex items-center gap-2 text-sm font-bold"><FileSearch className="h-4 w-4" />Authorized evidence</h3>
            <div className="mt-2 grid gap-2">
              {insight.evidence.map((item) => <article key={item.id} className="border border-stone-200 p-3"><p className="text-sm font-semibold">{item.title}</p><p className="mt-1 text-xs text-stone-600">{item.summary}</p><button type="button" onClick={()=>setSelectedEvidence(item)} className="mt-2 text-xs font-semibold text-[#a00028] underline">Open evidence</button></article>)}
            </div>
            {selectedEvidence&&<div role="dialog" aria-label="Evidence detail" className="mt-3 border-l-4 border-[#a00028] bg-stone-50 p-4"><p className="font-semibold">{selectedEvidence.title}</p><p className="mt-1 text-sm text-stone-600">{selectedEvidence.summary}</p><p className="mt-2 text-xs text-stone-500">Captured {new Date(selectedEvidence.capturedAt).toLocaleString()}</p></div>}
          </div>
          <aside className="bg-[#f4f1ed] p-4">
            <p className="text-xs font-bold uppercase tracking-wide text-stone-500">Proposed intervention</p>
            <p className="mt-2 text-sm leading-6">{insight.recommendations?.[0]?.explanation || `Review and resolve ${insight.primaryRisk}.`}</p>
            <p className="mt-3 text-xs text-stone-600">Confidence {Math.round(insight.confidence * 100)}% · No external writes</p>
            {status === "saved" ? <div role="status" className="mt-4 bg-emerald-50 p-3 text-sm font-semibold text-emerald-800"><p>Draft saved for human review. No external action was executed.</p><p className="mt-1 text-xs">Audit trail verified: {auditEvents.length} correlated events.</p></div> : <button type="button" onClick={saveDraft} disabled={status === "saving"} className="mt-4 inline-flex items-center gap-2 border border-[#a00028] px-3 py-2 text-sm font-semibold text-[#a00028] disabled:opacity-60"><ShieldCheck className="h-4 w-4" />{status === "saving" ? "Saving…" : "Save proposed intervention"}</button>}
          </aside>
        </div>
      )}
    </section>
  );
}
