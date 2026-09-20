/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowLeft, Bot, BrainCircuit, Database, FlaskConical, Gauge, KeyRound, Pencil, Play, RefreshCw, Settings2, ShieldCheck, Trash2, Wrench } from "lucide-react";
import { Link, Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import AgentDeletionDialog from "../../components/agents/AgentDeletionDialog";
import AgentTestConsole from "../../components/agents/AgentTestConsole";
import { getActivity, getAgent, getAgentAnalytics, getAgentEvaluations, getAgentExecutions, getAgentOptions, getAssignments, getEffectiveAccess, getVersions, lifecycleAgent, saveAssignments, updateAgent } from "../../services/agentService";

const tabs = [
  ["overview", "Overview", Activity], ["configuration", "Configuration", Settings2], ["capabilities", "Capabilities & tools", Wrench], ["knowledge", "Knowledge", Database], ["models", "Models & routing", BrainCircuit], ["evaluations", "Evaluations", FlaskConical], ["executions", "Executions", Gauge], ["versions", "Versions", RefreshCw], ["access", "Access & governance", KeyRound], ["test", "Test agent", Play],
];
const validTabs = new Set(tabs.map(([key]) => key));
const input = "mt-1 w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-[#a00028] focus:ring-2 focus:ring-[#a00028]/15";

export default function AgentWorkspacePage() {
  const { agentId, tab } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const client = useQueryClient();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [lifecycleBusy, setLifecycleBusy] = useState(false);
  const active = tab || "overview";
  const query = useQuery({ queryKey: ["agent", agentId], queryFn: () => getAgent(agentId), retry: false });
  if (!tab) return <Navigate replace to={`/agents/${agentId}/overview`} />;
  if (!validTabs.has(active)) return <Navigate replace to={`/agents/${agentId}/overview`} />;
  if (query.isLoading) return <main className="p-8 text-stone-600" aria-live="polite">Loading agent workspace…</main>;
  if (query.error) { const status = query.error.response?.status; return <main className="min-h-full bg-[#faf8f5] p-8"><h1 className="font-display text-3xl font-bold">{status === 403 ? "Access denied" : "Agent not found"}</h1><p className="mt-2 text-stone-600">This agent is unavailable or outside your authorized tenant scope.</p><Link to="/agents" className="mt-5 inline-block text-[#a00028]">Return to agents</Link></main>; }
  const agent = query.data;
  const returnTo = location.state?.from || "/agents";
  const refresh = async () => { await Promise.all([client.invalidateQueries({ queryKey: ["agent", agentId] }), client.invalidateQueries({ queryKey: ["agents"] })]); };
  async function lifecycle(action) { if (action === "disable" && !window.confirm("Disable this agent?")) return; setLifecycleBusy(true); setNotice(""); setActionError(""); try { await lifecycleAgent(agent.id, action, agent.lock_version, { change_note: `${action} from Agent workspace` }); setNotice(`Agent ${action} completed.`); await refresh(); } catch (error) { setActionError(error.response?.data?.detail?.message || `Unable to ${action} agent.`); } finally { setLifecycleBusy(false); } }
  async function deletionCompleted(action) { await refresh(); if (action === "deleted" || action === "archived") navigate(returnTo, { replace: true }); }
  return <main className="min-h-full bg-[#faf8f5] p-4 text-stone-900 md:p-8">
    <Link to={returnTo} className="inline-flex items-center gap-2 text-sm font-semibold text-stone-600 hover:text-[#a00028]"><ArrowLeft size={16} />Agents</Link>
    <header className="mt-5 flex flex-wrap items-start justify-between gap-4"><div><div className="flex flex-wrap items-center gap-3"><div className="grid h-11 w-11 place-items-center rounded-xl bg-[#a00028] text-white"><Bot /></div><div><h1 className="font-display text-3xl font-bold">{agent.name}</h1><p className="text-sm text-stone-500">{agent.slug} · version {agent.published_version || agent.current_version}</p></div><Status value={agent.lifecycle_status} /></div><p className="mt-3 max-w-3xl text-stone-600">{agent.description || "No description has been provided."}</p></div><div className="flex flex-wrap gap-2"><button onClick={() => query.refetch()} className="rounded-xl border border-stone-300 bg-white p-2.5" aria-label="Refresh agent"><RefreshCw size={17} /></button>{agent.permissions?.edit && agent.lifecycle_status !== "archived" && active !== "configuration" && <Link to={`/agents/${agent.id}/configuration`} state={{ from: returnTo }} className="inline-flex items-center gap-2 rounded-xl border border-stone-300 bg-white px-4 py-2 text-sm font-semibold"><Pencil size={16} />Edit</Link>}{agent.permissions?.publish && agent.lifecycle_status === "draft" && <button disabled={lifecycleBusy} onClick={() => lifecycle("publish")} className="rounded-xl bg-[#a00028] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Publish</button>}{agent.permissions?.disable && agent.lifecycle_status === "enabled" && <button disabled={lifecycleBusy} onClick={() => lifecycle("disable")} className="rounded-xl border border-stone-300 bg-white px-4 py-2 text-sm font-semibold disabled:opacity-50">Disable</button>}{(agent.permissions?.delete || agent.permissions?.archive) && <button onClick={() => setDeleteOpen(true)} className="inline-flex items-center gap-2 rounded-xl border border-red-200 bg-white px-4 py-2 text-sm font-semibold text-red-700"><Trash2 size={16} />Delete or archive</button>}</div></header>
    {notice && <p role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
    {actionError && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{actionError}</p>}
    <nav className="mt-6 overflow-x-auto border-b border-stone-300" aria-label="Agent sections"><div className="flex min-w-max gap-1">{tabs.map(([key, label, Icon]) => <Link key={key} to={`/agents/${agentId}/${key}`} state={{ from: returnTo }} aria-current={active === key ? "page" : undefined} className={`inline-flex items-center gap-2 border-b-2 px-3 py-3 text-sm font-semibold ${active === key ? "border-[#a00028] text-[#a00028]" : "border-transparent text-stone-500 hover:text-stone-900"}`}><Icon size={15} />{label}</Link>)}</div></nav>
    <section className="mt-6">{active === "overview" && <Overview agent={agent} />}{active === "configuration" && <Configuration agent={agent} onSaved={refresh} returnTo={returnTo} />}{active === "capabilities" && <Assignments agent={agent} kind="tools" />}{active === "knowledge" && <Assignments agent={agent} kind="knowledge" />}{active === "models" && <Models agent={agent} onSaved={refresh} />}{active === "evaluations" && <Evaluations agent={agent} />}{active === "executions" && <Executions agent={agent} navigate={navigate} />}{active === "versions" && <Versions agent={agent} />}{active === "access" && <Access agent={agent} />}{active === "test" && <AgentTestConsole agent={{ ...agent, uuid: agent.id }} />}</section>
    <AgentDeletionDialog agent={agent} open={deleteOpen} onOpenChange={setDeleteOpen} onCompleted={deletionCompleted} />
  </main>;
}

function Panel({ title, subtitle, children }) { return <article className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold">{title}</h2>{subtitle && <p className="mt-1 text-sm text-stone-500">{subtitle}</p>}<div className="mt-4">{children}</div></article>; }
function Status({ value }) { const tone = value === "enabled" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : value === "error" ? "border-red-200 bg-red-50 text-red-700" : value === "draft" ? "border-amber-200 bg-amber-50 text-amber-800" : "border-stone-200 bg-stone-100 text-stone-700"; return <span className={`rounded-full border px-2.5 py-1 text-xs font-bold uppercase ${tone}`}>{value}</span>; }
function Data({ rows }) { return <dl className="divide-y divide-stone-200 text-sm">{Object.entries(rows).map(([label, value]) => <div key={label} className="flex justify-between gap-5 py-3"><dt className="text-stone-500">{label}</dt><dd className="text-right font-semibold">{String(value ?? "Not available")}</dd></div>)}</dl>; }

function Overview({ agent }) { const activity = useQuery({ queryKey: ["agent", agent.id, "activity"], queryFn: () => getActivity(agent.id) }); const analytics = useQuery({ queryKey: ["agent", agent.id, "analytics", "overview"], queryFn: () => getAgentAnalytics(agent.id, {}) }); return <div className="space-y-4"><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"><Panel title="Lifecycle"><Data rows={{ Status: agent.lifecycle_status, Health: agent.operational_health, "Current version": agent.current_version, "Published version": agent.published_version || "None" }} /></Panel><Panel title="Model"><Data rows={{ Provider: agent.model_provider || "Not selected", Model: agent.model || "Not selected", Planner: agent.planner_configuration?.name || "default" }} /></Panel><Panel title="Execution health"><Data rows={{ Executions: analytics.data?.total_executions ?? "—", "Success rate": analytics.data?.success_rate == null ? "—" : `${analytics.data.success_rate}%`, "Average duration": analytics.data ? `${analytics.data.average_duration_ms} ms` : "—" }} /></Panel><Panel title="Governance"><Data rows={{ Owner: agent.owner_id, "Cost limit": agent.execution_limits?.cost_limit ?? "Not set", "Risk limit": agent.execution_limits?.risk_limit || "read", "Lock version": agent.lock_version }} /></Panel></div><Panel title="Purpose and responsibilities"><p className="text-sm leading-6 text-stone-700">{agent.instructions || "Instructions have not been configured."}</p></Panel><Panel title="Recent changes" subtitle="Immutable agent activity"><ol className="space-y-3">{(activity.data?.items || []).slice(0, 6).map((item) => <li key={item.id} className="border-l-2 border-[#a00028] pl-3 text-sm"><strong>{item.event_type}</strong><span className="block text-stone-500">{item.actor_id} · {new Date(item.created_at).toLocaleString()}</span></li>)}{!activity.data?.items?.length && <li className="text-sm text-stone-500">No recent changes.</li>}</ol></Panel></div>; }

function Configuration({ agent, onSaved, returnTo }) {
  const original = useMemo(() => ({
    name: agent.name,
    description: agent.description || "",
    owner_id: agent.owner_id || "",
    instructions: agent.instructions || "",
    environment: agent.environment_restrictions?.[0] || "development",
    max_steps: agent.execution_limits?.max_steps || 20,
    timeout_seconds: agent.execution_limits?.timeout_seconds || 120,
  }), [agent]);
  const [form, setForm] = useState(original);
  const [errors, setErrors] = useState({});
  const [message, setMessage] = useState("");
  const [saveError, setSaveError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => setForm(original), [original]);
  const dirty = JSON.stringify(form) !== JSON.stringify(original);
  useEffect(() => {
    const warn = (event) => { if (!dirty) return; event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  const editable = agent.lifecycle_status !== "archived" && agent.permissions?.edit;
  function set(name, value) { setForm((current) => ({ ...current, [name]: value })); setErrors((current) => ({ ...current, [name]: undefined })); }
  async function save(event) {
    event.preventDefault();
    if (saving) return;
    const nextErrors = {};
    if (form.name.trim().length < 2) nextErrors.name = "Enter at least two characters.";
    if (!form.owner_id.trim()) nextErrors.owner_id = "Owner is required.";
    if (Number(form.max_steps) < 1 || Number(form.max_steps) > 100) nextErrors.max_steps = "Enter a value from 1 to 100.";
    if (Number(form.timeout_seconds) < 1 || Number(form.timeout_seconds) > 3600) nextErrors.timeout_seconds = "Enter a value from 1 to 3600.";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    setSaving(true);
    setMessage("");
    setSaveError("");
    try {
      await updateAgent(agent.id, {
        name: form.name.trim(),
        description: form.description,
        owner_id: form.owner_id.trim(),
        instructions: form.instructions,
        execution_limits: {
          ...agent.execution_limits,
          max_steps: Number(form.max_steps),
          timeout_seconds: Number(form.timeout_seconds),
          environments: [form.environment],
        },
        change_note: "Configuration updated from Agent editor",
      }, agent.lock_version);
      setMessage(agent.published_version ? `Draft version ${agent.current_version + 1} saved. Published version ${agent.published_version} remains immutable.` : "Agent changes saved.");
      await onSaved();
    } catch (error) {
      const detail = error.response?.data?.detail;
      setSaveError(error.response?.status === 409 ? "This agent changed. Refresh before saving." : detail?.message || "Configuration could not be saved.");
    } finally {
      setSaving(false);
    }
  }
  return <Panel title="Edit agent" subtitle={editable ? agent.published_version ? `Changes create a new draft; published version ${agent.published_version} remains active.` : `Editing draft version ${agent.current_version}.` : "You do not have permission to edit this agent."}>
    <form onSubmit={save} className="grid gap-4 md:grid-cols-2">
      <Field label="Name" error={errors.name}><input disabled={!editable} className={input} value={form.name} onChange={(event) => set("name", event.target.value)} /></Field>
      <Field label="Owner" error={errors.owner_id}><input disabled={!editable} className={input} value={form.owner_id} onChange={(event) => set("owner_id", event.target.value)} /></Field>
      <Field label="Description" className="md:col-span-2"><textarea disabled={!editable} className={`${input} min-h-24`} value={form.description} onChange={(event) => set("description", event.target.value)} /></Field>
      <Field label="System instructions" className="md:col-span-2"><textarea disabled={!editable} className={`${input} min-h-48`} value={form.instructions} onChange={(event) => set("instructions", event.target.value)} /></Field>
      <Field label="Environment"><select disabled={!editable} className={input} value={form.environment} onChange={(event) => set("environment", event.target.value)}>{["development", "staging", "production"].map((value) => <option key={value}>{value}</option>)}</select></Field>
      <Field label="Maximum steps" error={errors.max_steps}><input disabled={!editable} type="number" min="1" max="100" className={input} value={form.max_steps} onChange={(event) => set("max_steps", event.target.value)} /></Field>
      <Field label="Timeout seconds" error={errors.timeout_seconds}><input disabled={!editable} type="number" min="1" max="3600" className={input} value={form.timeout_seconds} onChange={(event) => set("timeout_seconds", event.target.value)} /></Field>
      <div className="rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm md:col-span-2"><strong>Related configuration</strong><p className="mt-1 text-stone-600">Manage the governed model, tools and knowledge without duplicating their existing editors.</p><div className="mt-3 flex flex-wrap gap-3"><Link state={{ from: returnTo }} className="font-semibold text-[#a00028]" to={`/agents/${agent.id}/models`}>Model & routing</Link><Link state={{ from: returnTo }} className="font-semibold text-[#a00028]" to={`/agents/${agent.id}/capabilities`}>Capabilities & tools</Link><Link state={{ from: returnTo }} className="font-semibold text-[#a00028]" to={`/agents/${agent.id}/knowledge`}>Knowledge sources</Link></div></div>
      {message && <p role="status" className="text-sm text-emerald-700 md:col-span-2">{message}</p>}
      {saveError && <p role="alert" className="text-sm text-red-700 md:col-span-2">{saveError}</p>}
      {editable && <div className="flex flex-wrap gap-2 md:col-span-2"><button disabled={saving || !dirty} className="rounded-xl bg-[#a00028] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? "Saving…" : "Save changes"}</button><button type="button" disabled={saving || !dirty} onClick={() => { setForm(original); setErrors({}); }} className="rounded-xl border border-stone-300 bg-white px-4 py-2 text-sm font-semibold disabled:opacity-50">Reset</button><Link to={returnTo} onClick={(event) => { if (dirty && !window.confirm("Discard unsaved Agent changes?")) event.preventDefault(); }} className="rounded-xl px-4 py-2 text-sm font-semibold text-stone-600">Cancel</Link></div>}
    </form>
  </Panel>;
}

function Field({ label, error, className = "", children }) { return <label className={`text-sm font-semibold ${className}`}>{label}{children}{error && <span className="mt-1 block text-xs text-red-700">{error}</span>}</label>; }

function Assignments({ agent, kind }) { const query = useQuery({ queryKey: ["agent", agent.id, kind], queryFn: () => getAssignments(agent.id, kind) }); const options = useQuery({ queryKey: ["agent-options"], queryFn: getAgentOptions }); const [selected, setSelected] = useState([]); const [message, setMessage] = useState(""); useEffect(() => { if (query.data) setSelected(query.data); }, [query.data]); if (query.isLoading || options.isLoading) return <p>Loading {kind}…</p>; const editable = agent.lifecycle_status === "draft"; const available = kind === "tools" ? options.data.tools : options.data.knowledge; const key = kind === "tools" ? "tool_name" : "knowledge_source_id"; function add(value) { if (!value || selected.some((item) => String(item[key]) === String(value))) return; const item = kind === "tools" ? { tool_name: value, version_restriction: "active", assignment_action: "execute", enabled: true, risk_mode: options.data.tools.find((tool) => tool.name === value)?.risk || "read", approval_required: false } : { knowledge_source_id: Number(value), access_mode: "retrieve", readiness_required: true, enabled: true }; setSelected([...selected, item]); } async function save() { await saveAssignments(agent.id, kind, selected.map((item) => { const copy = { ...item }; ["id", "created_at", "added_by", "agent_version", "source_type"].forEach((fieldName) => delete copy[fieldName]); return copy; })); setMessage("Assignments saved."); query.refetch(); } return <Panel title={kind === "tools" ? "Capabilities and tools" : "Knowledge and context"} subtitle={editable ? "Assignments apply to this draft only." : "Published assignments are read-only."}><select disabled={!editable} className={input} defaultValue="" onChange={(event) => { add(event.target.value); event.target.value = ""; }}><option value="">Add {kind === "tools" ? "approved tool" : "approved knowledge source"}…</option>{available.map((item) => <option key={item.name || item.id} value={item.name || item.id}>{item.display_name || item.name} · {item.risk || item.readiness}</option>)}</select><div className="mt-4 grid gap-3 md:grid-cols-2">{selected.map((item) => <div key={item[key]} className="rounded-xl border border-stone-200 bg-stone-50 p-4"><div className="flex justify-between"><strong>{kind === "tools" ? item.tool_name : available.find((source) => source.id === item.knowledge_source_id)?.name || item.knowledge_source_id}</strong>{editable && <button onClick={() => setSelected(selected.filter((entry) => entry[key] !== item[key]))} className="text-sm text-[#a00028]">Remove</button>}</div><p className="mt-2 text-xs text-stone-500">{kind === "tools" ? `${item.risk_mode} · ${item.approval_required ? "Approval required" : "Governance evaluated at runtime"}` : `${item.access_mode} · ${item.readiness_required ? "Readiness required" : "Optional readiness"}`}</p></div>)}</div>{editable && <button onClick={save} className="mt-4 rounded-xl bg-[#a00028] px-4 py-2 text-sm font-semibold text-white">Save assignments</button>}{message && <p className="mt-3 text-sm text-stone-600">{message}</p>}</Panel>; }

function Models({ agent, onSaved }) { const options = useQuery({ queryKey: ["agent-options"], queryFn: getAgentOptions }); const current = `${agent.model_configuration?.provider || ""}:${agent.model_configuration?.model || ""}`; const [selection, setSelection] = useState(current); const [message, setMessage] = useState(""); if (options.isLoading) return <p>Loading governed models…</p>; const editable = agent.lifecycle_status === "draft" && agent.permissions?.edit; async function save() { const [provider, ...modelParts] = selection.split(":"); await updateAgent(agent.id, { model_configuration: { ...agent.model_configuration, provider, model: modelParts.join(":") }, change_note: "Governed model updated" }, agent.lock_version); setMessage("Model routing saved as a new draft version."); onSaved(); } return <div className="grid gap-4 lg:grid-cols-2"><Panel title="Primary model" subtitle="Only allowlisted models are selectable"><select disabled={!editable} className={input} value={selection} onChange={(event) => setSelection(event.target.value)}>{options.data.models.map((model) => <option key={`${model.provider}:${model.model}`} value={`${model.provider}:${model.model}`}>{model.label} · {model.provider}</option>)}</select>{editable && <button onClick={save} className="mt-4 rounded-xl bg-[#a00028] px-4 py-2 text-sm font-semibold text-white">Save routing</button>}{message && <p className="mt-3 text-sm text-stone-600">{message}</p>}</Panel><Panel title="Effective routing policy"><Data rows={{ Provider: agent.model_configuration?.provider || "Not selected", Model: agent.model_configuration?.model || "Not selected", Fallback: agent.model_configuration?.fallback || "None", "Cost limit": agent.execution_limits?.cost_limit ?? "Not set", Decision: "Governance evaluated at runtime" }} /></Panel></div>; }

function Evaluations({ agent }) { const query = useQuery({ queryKey: ["agent", agent.id, "evaluations"], queryFn: () => getAgentEvaluations(agent.id) }); if (query.isLoading) return <p>Loading evaluations…</p>; return <Panel title="Evaluation history" subtitle="Persisted controlled runs using governed datasets and models"><Table headers={["Status", "Version", "Dataset", "Model", "Failures", "Started"]} rows={(query.data?.items || []).map((run) => [run.status, `v${run.agent_version}`, `${run.dataset_id} · v${run.dataset_version}`, run.model_id, run.failures?.length || 0, new Date(run.started_at).toLocaleString()])} empty="No controlled evaluation has been run for this agent." /></Panel>; }
function Executions({ agent, navigate }) { const query = useQuery({ queryKey: ["agent", agent.id, "executions"], queryFn: () => getAgentExecutions(agent.id, { page: 1, page_size: 50 }) }); if (query.isLoading) return <p>Loading executions…</p>; return <Panel title="Execution history" subtitle="Durable runtime executions with usage and correlation"><Table headers={["Status", "Execution", "Version", "Actor", "Mode", "Model", "Duration", "Cost", "Started"]} rows={(query.data?.items || []).map((run) => [run.status, <button className="font-semibold text-[#a00028]" onClick={() => navigate(`/agents/${agent.id}/executions/${run.execution_id}`)}>{run.execution_id.slice(0, 8)}</button>, `v${run.agent_version}`, run.actor_id, run.test_mode ? "Test" : "Production", run.model_name, run.duration_ms == null ? "—" : `${run.duration_ms} ms`, run.actual_cost ?? run.estimated_cost ?? "—", new Date(run.started_at).toLocaleString()])} empty="No executions have been recorded." /></Panel>; }
function Versions({ agent }) { const query = useQuery({ queryKey: ["agent", agent.id, "versions"], queryFn: () => getVersions(agent.id) }); if (query.isLoading) return <p>Loading versions…</p>; return <div className="grid gap-4 lg:grid-cols-2">{(query.data || []).map((version) => <Panel key={version.version} title={`Version ${version.version}`} subtitle={version.published ? "Published immutable version" : "Draft version"}><Data rows={{ Creator: version.created_by, Created: new Date(version.created_at).toLocaleString(), Model: version.model_configuration?.model || "Not selected", Planner: version.planner_configuration?.name || "default", Change: version.change_note }} /><p className="mt-4 line-clamp-4 text-sm text-stone-600">{version.instructions || "No instructions."}</p></Panel>)}</div>; }
function Access({ agent }) { const assignments = useQuery({ queryKey: ["agent", agent.id, "access"], queryFn: () => getAssignments(agent.id, "access") }); const effective = useQuery({ queryKey: ["agent", agent.id, "effective-access"], queryFn: () => getEffectiveAccess(agent.id, "view") }); if (assignments.isLoading || effective.isLoading) return <p>Loading access policy…</p>; return <div className="grid gap-4 lg:grid-cols-2"><Panel title="Ownership and effective access"><Data rows={{ Owner: agent.owner_id, Decision: effective.data.decision, Reason: effective.data.reason_codes.join(", "), "Explicit denies": effective.data.explicit_denies.length, "Approval required": effective.data.approval_required ? "Yes" : "No" }} /></Panel><Panel title="Access assignments"><Table headers={["Subject type", "Subject", "Action", "Enabled"]} rows={(assignments.data || []).map((item) => [item.subject_type, item.subject_id, item.action, item.enabled ? "Yes" : "No"])} empty="No object-level assignments." /></Panel><Panel title="Governance policy"><Data rows={{ "Tenant scope": "Current authenticated tenant", "Environment scope": (agent.environment_restrictions || []).join(", ") || "None", "Risk limit": agent.execution_limits?.risk_limit || "read", "Tool discovery": agent.tool_discovery_configuration?.mode || "assigned_only" }} /></Panel></div>; }
function Table({ headers, rows, empty }) { if (!rows.length) return <p className="rounded-xl border border-dashed border-stone-300 p-6 text-center text-sm text-stone-500">{empty}</p>; return <div className="overflow-x-auto"><table className="min-w-[720px] w-full text-left text-sm"><thead className="bg-stone-50 text-xs uppercase text-stone-500"><tr>{headers.map((header) => <th className="p-3" key={header}>{header}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr className="border-t border-stone-200" key={index}>{row.map((cell, cellIndex) => <td className="p-3" key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div>; }

void ShieldCheck;
