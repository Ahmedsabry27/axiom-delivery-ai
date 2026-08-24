import { useState } from "react";
import { Play, Square } from "lucide-react";
import { cancelAgentExecution, resumeAgent, testAgent } from "../../services/agentService";

const control = "mt-2 w-full rounded-xl border border-stone-300 bg-white p-3 text-sm outline-none focus:border-[#a00028] focus:ring-2 focus:ring-[#a00028]/15";

export default function AgentTestConsole({ agent }) {
  const [prompt, setPrompt] = useState("Generate a deployment report");
  const [result, setResult] = useState(null);
  const [fields, setFields] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const agentId = agent.uuid || agent.id;
  async function run() { setBusy(true); setError(""); try { setResult(await testAgent(agentId, { message: prompt, inputs: {} })); } catch (requestError) { setError(requestError.response?.data?.detail?.message || "Test execution failed safely."); } finally { setBusy(false); } }
  async function submit() { setBusy(true); setError(""); try { const continuation = result.continuation; setResult(await resumeAgent(result.execution_id, continuation.kind, { resume_token: continuation.resume_token, response: fields })); } catch (requestError) { setError(requestError.response?.data?.detail?.message || "Resume failed safely."); } finally { setBusy(false); } }
  async function cancel() { setResult(await cancelAgentExecution(agentId, result.execution_id)); }
  const continuation = result?.continuation;
  return <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm" aria-label="Agent Test Console">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-bold">Test agent</h2><p className="mt-1 text-sm text-stone-500">Safe persisted test mode · version {agent.published_version || agent.current_version || "—"} · runtime permissions and budget controls remain active</p></div>{result && !["succeeded", "failed", "cancelled"].includes(result.status) && <button onClick={cancel} className="inline-flex items-center gap-2 rounded-xl border border-red-300 px-3 py-2 text-sm font-semibold text-red-700"><Square size={14} />Cancel</button>}</div>
    <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><strong>Safe test mode:</strong> external mutations remain proposals or use approved test adapters.</div>
    <label className="mt-4 block text-sm font-semibold">Test prompt<textarea className={`${control} min-h-28`} value={prompt} onChange={(event) => setPrompt(event.target.value)} /></label>
    <button disabled={busy || !agentId || !prompt.trim()} onClick={run} className="mt-3 inline-flex items-center gap-2 rounded-xl bg-[#a00028] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><Play size={14} />{busy ? "Running…" : "Run test"}</button>
    {error && <p role="alert" className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
    {result && <div className="mt-5 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm"><dl className="grid gap-3 sm:grid-cols-3"><div><dt className="text-stone-500">Status</dt><dd className="font-semibold">{result.status}</dd></div><div><dt className="text-stone-500">Execution</dt><dd className="font-mono">{result.execution_id}</dd></div><div><dt className="text-stone-500">Correlation</dt><dd className="font-mono">{result.correlation_id}</dd></div></dl>{result.result?.message && <pre className="mt-4 whitespace-pre-wrap rounded-lg bg-white p-3 text-sm">{result.result.message}</pre>}</div>}
    {continuation?.kind === "input" && <form className="mt-4 space-y-3" onSubmit={(event) => { event.preventDefault(); submit(); }}>{continuation.missing_fields.map((name) => <label className="block text-sm font-semibold" key={name}>{name.replaceAll("_", " ")}<input required className={control} value={fields[name] || ""} onChange={(event) => setFields({ ...fields, [name]: event.target.value })} /></label>)}<button className="rounded-xl bg-[#a00028] px-4 py-2 text-sm font-semibold text-white">Resume execution</button></form>}
    {continuation?.kind === "approval" && <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Approval required. A different authorized approver must review this execution.</p>}
  </section>;
}
