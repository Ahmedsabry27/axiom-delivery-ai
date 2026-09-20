import { useDeferredValue, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import {
  Activity,
  Archive,
  Bot,
  Eye,
  MoreHorizontal,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  Trash2,
  Pause,
} from "lucide-react";
import AgentDeletionDialog from "../../components/agents/AgentDeletionDialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../../components/ui/dropdown-menu";
import { useAgents } from "../../hooks/useAgents";
import { lifecycleAgent } from "../../services/agentService";

const statuses = ["", "draft", "published", "enabled", "disabled", "archived", "error"];
const field = "h-10 w-full rounded-xl border border-stone-300 bg-white px-3 text-sm text-stone-800 outline-none placeholder:text-stone-400 focus:border-[#a00028] focus:ring-2 focus:ring-[#a00028]/15";

export default function AgentsPage() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const search = useDeferredValue(params.get("search") || "");
  const filters = {
    search,
    status: params.get("status") || undefined,
    owner: params.get("owner") || undefined,
    model: params.get("model") || undefined,
    environment: params.get("environment") || undefined,
    include_archived: params.get("archived") === "true",
    sort: params.get("sort") || "updated_at",
    direction: params.get("direction") || "desc",
    page: Number(params.get("page") || 1),
    page_size: Number(params.get("page_size") || 10),
  };
  const query = useAgents(filters);
  const data = query.data || { items: [], total: 0, pages: 1, page: 1, permissions: {} };
  const returnTo = `${location.pathname}${location.search}`;
  const update = (key, value) => setParams((current) => {
    const next = new URLSearchParams(current);
    value ? next.set(key, value) : next.delete(key);
    if (key !== "page") next.set("page", "1");
    return next;
  });
  const executions = data.items.reduce((sum, item) => sum + (item.execution_count || 0), 0);
  const success = executions
    ? data.items.reduce((sum, item) => sum + (item.execution_count || 0) * (item.success_rate || 0), 0) / executions
    : null;
  const attention = data.items.filter((item) => item.lifecycle_status === "error" || item.operational_health === "error" || (item.success_rate != null && item.success_rate < 80)).length;
  const canCreate = data.permissions?.create === true;

  async function changeLifecycle(agent, action) {
    if (busyId) return;
    setBusyId(agent.id);
    setNotice("");
    setActionError("");
    try {
      await lifecycleAgent(agent.id, action, agent.lock_version, { change_note: `${action} from Agent directory` });
      setNotice(`${agent.name} was ${action === "enable" ? "enabled" : "disabled"}.`);
      await queryClient.invalidateQueries({ queryKey: ["agents"] });
    } catch (error) {
      setActionError(error.response?.data?.detail?.message || `Unable to ${action} ${agent.name}.`);
    } finally {
      setBusyId(null);
    }
  }

  async function mutationCompleted(action) {
    setNotice(`${deleteTarget.name} was ${action}.`);
    setDeleteTarget(null);
    await queryClient.invalidateQueries({ queryKey: ["agents"] });
  }

  const actions = (agent) => ({
    view: () => navigate(`/agents/${agent.id}/overview`, { state: { from: returnTo } }),
    edit: () => navigate(`/agents/${agent.id}/configuration`, { state: { from: returnTo } }),
    lifecycle: (action) => changeLifecycle(agent, action),
    remove: () => setDeleteTarget(agent),
  });

  return <main className="min-h-full bg-[#faf8f5] p-4 text-stone-900 md:p-8">
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-[#a00028]">Automation</p><h1 className="mt-2 font-display text-4xl font-bold">Agents</h1><p className="mt-2 text-stone-600">Build and govern specialized AI delivery agents</p></div>
      <div className="flex items-center gap-2"><span className="hidden text-xs text-stone-500 sm:inline">Last refreshed {query.dataUpdatedAt ? new Date(query.dataUpdatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}</span><button aria-label="Refresh Agents" onClick={() => query.refetch()} className="grid h-10 w-10 place-items-center rounded-xl border border-stone-300 bg-white"><RefreshCw size={18} className={query.isFetching ? "animate-spin" : ""} /></button>{canCreate && <Link to="/agents/new" className="inline-flex h-10 items-center gap-2 rounded-xl bg-[#a00028] px-4 text-sm font-semibold text-white"><Plus size={16} />Create agent</Link>}</div>
    </header>

    {notice && <p role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
    {actionError && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{actionError}</p>}

    <section className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5" aria-label="Agent portfolio summary">
      <Metric label="Total agents" value={query.isLoading ? "—" : data.total} detail="Accessible agents · current filter" icon={Bot} />
      <Metric label="Published" value={query.isLoading ? "—" : data.items.filter((item) => ["published", "enabled"].includes(item.lifecycle_status)).length} detail="Visible page · current filter" icon={Activity} />
      <Metric label="Drafts" value={query.isLoading ? "—" : data.items.filter((item) => item.lifecycle_status === "draft").length} detail="Visible page · editable versions" icon={Bot} />
      <Metric label="Success rate" value={query.isLoading || success == null ? "—" : `${success.toFixed(1)}%`} detail={query.isLoading ? "Loading execution metrics" : `${executions} executions · visible page`} icon={Activity} />
      <Metric label="Needs attention" value={query.isLoading ? "—" : attention} detail="Error state or success below 80%" icon={ShieldAlert} />
    </section>

    <section className="mt-6 grid items-end gap-3 rounded-2xl border border-stone-300 bg-white p-4 shadow-sm sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8" aria-label="Agent directory filters">
      <FilterLabel label="Search agents" className="lg:col-span-2"><span className="relative block"><Search className="absolute left-3 top-3 text-stone-400" size={16} /><input aria-label="Search Agents" value={params.get("search") || ""} onChange={(event) => update("search", event.target.value)} className={`${field} pl-9`} placeholder="Name, slug or description" /></span></FilterLabel>
      <Select label="Status" value={filters.status || ""} onChange={(value) => update("status", value)} options={statuses} />
      <FilterLabel label="Owner"><input aria-label="Owner filter" value={filters.owner || ""} onChange={(event) => update("owner", event.target.value)} className={field} placeholder="Any owner" /></FilterLabel>
      <FilterLabel label="Model"><input aria-label="Model filter" value={filters.model || ""} onChange={(event) => update("model", event.target.value)} className={field} placeholder="Any model" /></FilterLabel>
      <Select label="Environment" value={filters.environment || ""} onChange={(value) => update("environment", value)} options={["", "development", "staging", "production"]} />
      <Select label="Sort by" value={filters.sort} onChange={(value) => update("sort", value)} options={[{ value: "updated_at", label: "Updated" }, { value: "name", label: "Name" }, { value: "lifecycle", label: "Status" }, { value: "owner", label: "Owner" }]} />
      <Select label="Direction" value={filters.direction} onChange={(value) => update("direction", value)} options={[{ value: "desc", label: "Descending" }, { value: "asc", label: "Ascending" }]} />
      <label className="flex h-10 items-center gap-2 text-sm font-semibold text-stone-600 sm:col-span-2 lg:col-span-1"><input type="checkbox" checked={filters.include_archived} onChange={(event) => update("archived", event.target.checked ? "true" : "")} className="h-4 w-4 accent-[#a00028]" />Include archived</label>
    </section>

    <DirectoryState query={query} filtered={Boolean(search || filters.status || filters.owner || filters.model || filters.environment)}>
      <div className="mt-5 grid gap-3 md:hidden">{data.items.map((agent) => <AgentCard key={agent.id} agent={agent} actions={actions(agent)} busy={busyId === agent.id} returnTo={returnTo} />)}</div>
      <AgentTable agents={data.items} actionFactory={actions} busyId={busyId} returnTo={returnTo} />
    </DirectoryState>
    <nav className="mt-4 flex flex-wrap items-center justify-between gap-3" aria-label="Agent directory pagination"><span className="text-sm text-stone-500">{data.total} results · page {data.page} of {data.pages}</span><div className="flex gap-2"><button aria-label="Previous page" disabled={data.page <= 1} onClick={() => update("page", String(data.page - 1))} className="h-10 rounded-xl border border-stone-300 bg-white px-3 disabled:opacity-40">Previous</button><button aria-label="Next page" disabled={data.page >= data.pages} onClick={() => update("page", String(data.page + 1))} className="h-10 rounded-xl border border-stone-300 bg-white px-3 disabled:opacity-40">Next</button></div></nav>

    <AgentDeletionDialog agent={deleteTarget} open={Boolean(deleteTarget)} onOpenChange={(open) => !open && setDeleteTarget(null)} onCompleted={mutationCompleted} />
  </main>;
}

function AgentTable({ agents, actionFactory, busyId, returnTo }) {
  return <div className="mt-5 hidden overflow-hidden rounded-2xl border border-stone-300 bg-white shadow-sm md:block"><table className="w-full table-fixed text-left text-sm"><caption className="sr-only">Agent directory</caption><thead className="bg-stone-50 text-xs uppercase tracking-wide text-stone-500"><tr><th className="w-[27%] px-4 py-3">Agent</th><th className="w-[12%] px-3 py-3">Status</th><th className="w-[8%] px-3 py-3">Version</th><th className="hidden w-[12%] px-3 py-3 xl:table-cell">Owner</th><th className="hidden w-[15%] px-3 py-3 lg:table-cell">Model</th><th className="hidden w-[13%] px-3 py-3 lg:table-cell">Capabilities</th><th className="w-[13%] px-3 py-3">Last execution</th><th className="hidden w-[9%] px-3 py-3 xl:table-cell">Success</th><th className="w-[12%] px-3 py-3">Updated</th><th className="w-14 px-2 py-3 text-center">Actions</th></tr></thead><tbody>{agents.map((agent) => <tr key={agent.id} className="border-t border-stone-200 hover:bg-stone-50"><td className="px-4 py-3"><Link state={{ from: returnTo }} className="block truncate font-semibold text-[#a00028] hover:underline" title={agent.name} to={`/agents/${agent.id}/overview`}>{agent.name}</Link><small className="block truncate text-stone-500" title={agent.description || agent.slug}>{agent.description || agent.slug}</small></td><td className="px-3 py-3"><Status value={agent.lifecycle_status} /></td><td className="px-3 py-3">v{agent.published_version || agent.current_version}</td><td className="hidden truncate px-3 py-3 xl:table-cell" title={agent.owner_id}>{agent.owner_id || "—"}</td><td className="hidden truncate px-3 py-3 lg:table-cell" title={agent.model || "No model selected"}>{agent.model || "—"}</td><td className="hidden px-3 py-3 lg:table-cell"><Capabilities agent={agent} /></td><td className="px-3 py-3"><Time value={agent.last_execution_at} never /></td><td className="hidden px-3 py-3 xl:table-cell">{agent.success_rate == null ? "—" : `${agent.success_rate}%`}</td><td className="px-3 py-3 text-stone-500"><Time value={agent.updated_at} /></td><td className="px-2 py-3 text-center"><AgentActions agent={agent} actions={actionFactory(agent)} busy={busyId === agent.id} /></td></tr>)}</tbody></table></div>;
}

function Metric({ label, value, detail, icon: Icon }) { return <article className="rounded-2xl border border-stone-300 bg-white p-4 shadow-sm"><div className="flex justify-between"><p className="text-xs font-bold uppercase tracking-wide text-stone-500">{label}</p><Icon size={18} className="text-[#a00028]" /></div><p className="mt-3 text-3xl font-bold">{value}</p><p className="mt-2 text-xs text-stone-500">{detail}</p></article>; }
function Status({ value }) { const tone = value === "enabled" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : value === "error" ? "border-red-200 bg-red-50 text-red-700" : value === "draft" ? "border-amber-200 bg-amber-50 text-amber-800" : value === "archived" ? "border-stone-300 bg-stone-100 text-stone-500" : "border-stone-200 bg-stone-100 text-stone-700"; return <span className={`inline-block max-w-full truncate rounded-full border px-2.5 py-1 text-xs font-semibold capitalize ${tone}`} title={value}>{value}</span>; }
function Capabilities({ agent }) { if (agent.tool_count == null && agent.knowledge_count == null) return "—"; return <span title={`${agent.tool_count || 0} tools and ${agent.knowledge_count || 0} knowledge sources`}>{agent.tool_count || 0} tools · {agent.knowledge_count || 0} sources</span>; }
function Time({ value, never = false }) { if (!value) return never ? "Never" : "—"; const exact = new Date(value).toLocaleString(); return <time dateTime={value} title={exact}>{relativeTime(value)}</time>; }
function relativeTime(value) { const seconds = Math.round((new Date(value).getTime() - Date.now()) / 1000); const ranges = [[60, "second"], [60, "minute"], [24, "hour"], [7, "day"], [4.345, "week"], [12, "month"], [Infinity, "year"]]; let amount = seconds; for (const [limit, unit] of ranges) { if (Math.abs(amount) < limit) return new Intl.RelativeTimeFormat(undefined, { numeric: "auto" }).format(Math.round(amount), unit); amount /= limit; } return exactFallback(value); }
function exactFallback(value) { return new Date(value).toLocaleDateString(); }

function AgentCard({ agent, actions, busy, returnTo }) { return <article className="rounded-2xl border border-stone-300 bg-white p-4 shadow-sm"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><Link state={{ from: returnTo }} className="block truncate font-semibold text-[#a00028]" to={`/agents/${agent.id}/overview`}>{agent.name}</Link><p className="mt-1 line-clamp-2 text-sm text-stone-500">{agent.description || agent.slug}</p></div><div className="flex items-center gap-1"><Status value={agent.lifecycle_status} /><AgentActions agent={agent} actions={actions} busy={busy} /></div></div><dl className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><dt className="text-stone-500">Model</dt><dd className="truncate" title={agent.model || "No model selected"}>{agent.model || "—"}</dd></div><div><dt className="text-stone-500">Owner</dt><dd className="truncate" title={agent.owner_id}>{agent.owner_id || "—"}</dd></div><div><dt className="text-stone-500">Capabilities</dt><dd><Capabilities agent={agent} /></dd></div><div><dt className="text-stone-500">Success</dt><dd>{agent.success_rate == null ? "—" : `${agent.success_rate}%`}</dd></div><div><dt className="text-stone-500">Last execution</dt><dd><Time value={agent.last_execution_at} never /></dd></div><div><dt className="text-stone-500">Updated</dt><dd><Time value={agent.updated_at} /></dd></div></dl></article>; }

function AgentActions({ agent, actions, busy }) {
  const permissions = agent.permissions || {};
  const canEnable = permissions.enable && ["published", "disabled"].includes(agent.lifecycle_status);
  const canDisable = permissions.disable && agent.lifecycle_status === "enabled";
  const canRemove = permissions.delete || permissions.archive;
  return <DropdownMenu><DropdownMenuTrigger asChild><button disabled={busy} aria-label={`Actions for ${agent.name}`} className="grid h-9 w-9 place-items-center rounded-lg text-stone-600 hover:bg-stone-100 disabled:opacity-50"><MoreHorizontal size={18} /></button></DropdownMenuTrigger><DropdownMenuContent align="end" className="w-44 bg-white text-stone-900"><DropdownMenuItem onSelect={actions.view}><Eye />View</DropdownMenuItem>{permissions.edit && agent.lifecycle_status !== "archived" && <DropdownMenuItem onSelect={actions.edit}><Pencil />Edit</DropdownMenuItem>}{(canEnable || canDisable) && <><DropdownMenuSeparator />{canEnable && <DropdownMenuItem onSelect={() => actions.lifecycle("enable")}><Play />Enable</DropdownMenuItem>}{canDisable && <DropdownMenuItem onSelect={() => actions.lifecycle("disable")}><Pause />Disable</DropdownMenuItem>}</>}{canRemove && <><DropdownMenuSeparator /><DropdownMenuItem variant="destructive" onSelect={actions.remove}>{permissions.delete ? <Trash2 /> : <Archive />}{permissions.delete ? "Delete or archive" : "Archive"}</DropdownMenuItem></>}</DropdownMenuContent></DropdownMenu>;
}

function FilterLabel({ label, className = "", children }) { return <label className={`grid gap-1 text-xs font-semibold text-stone-600 ${className}`}><span>{label}</span>{children}</label>; }
function Select({ label, value, onChange, options }) { return <FilterLabel label={label}><select aria-label={`${label} filter`} value={value} onChange={(event) => onChange(event.target.value)} className={field}>{options.map((item) => { const option = typeof item === "string" ? { value: item, label: item || "All" } : item; return <option key={option.value || "all"} value={option.value}>{option.label}</option>; })}</select></FilterLabel>; }
function DirectoryState({ query, filtered, children }) { if (query.isLoading) return <section aria-live="polite" className="mt-5 grid gap-3"><div className="h-16 animate-pulse rounded-2xl bg-stone-200" /><div className="h-16 animate-pulse rounded-2xl bg-stone-200" /><span className="sr-only">Loading agents…</span></section>; if (query.error) { const status = query.error.response?.status; return <section role="alert" className="mt-8 rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800"><h2 className="font-semibold">{status === 401 ? "Authentication required" : status === 403 ? "Permission denied" : status >= 500 ? "Server unavailable" : "Agents could not be loaded"}</h2><button onClick={() => query.refetch()} className="mt-3 rounded-xl bg-[#a00028] px-4 py-2 text-white">Retry</button></section>; } if (!query.data?.items?.length) return <section className="mt-8 rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center"><Bot className="mx-auto text-stone-400" /><h2 className="mt-3 font-semibold">{filtered ? "No agents match these filters" : "No agents yet"}</h2><p className="mt-1 text-stone-500">{filtered ? "Clear or adjust the directory filters." : "Create a governed agent to begin."}</p></section>; return children; }
