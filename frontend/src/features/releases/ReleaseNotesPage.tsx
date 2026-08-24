import { useMemo, useState } from "react";
import { Copy, Download, ExternalLink, FileText, Search, ShieldCheck, Wrench, X } from "lucide-react";
import { Link } from "react-router-dom";
import type { Release, ReleaseNoteCategory, ReleaseNoteItem } from "./types";

const CATEGORY_LABELS: Record<ReleaseNoteCategory, string> = {
  FEATURE: "New Features",
  ENHANCEMENT: "Enhancements",
  BUG_FIX: "Bug Fixes",
  TECHNICAL: "Technical Changes",
  SECURITY: "Security Improvements",
  PERFORMANCE: "Performance Improvements",
  KNOWN_ISSUE: "Known Issues",
  DEPRECATED: "Deprecated / Removed",
};

const CATEGORY_ORDER = Object.keys(CATEGORY_LABELS) as ReleaseNoteCategory[];

function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "success" | "warning" | "danger" | "purple" }) {
  const styles = { neutral: "border-stone-200 bg-stone-100 text-stone-700", success: "border-emerald-200 bg-emerald-50 text-emerald-700", warning: "border-amber-200 bg-amber-50 text-amber-800", danger: "border-rose-200 bg-rose-50 text-rose-700", purple: "border-violet-200 bg-violet-50 text-violet-700" }[tone];
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold ${styles}`}>{children}</span>;
}

function SummaryCard({ label, value, icon: Icon }: { label: string; value: number; icon: typeof FileText }) {
  return <div className="rounded-2xl border border-stone-300 bg-white p-4 shadow-sm"><div className="flex items-start justify-between"><div><p className="text-[11px] font-bold uppercase tracking-[0.16em] text-stone-500">{label}</p><p className="mt-3 text-3xl font-bold text-stone-900">{value}</p></div><Icon className="h-5 w-5 text-[#a00028]" /></div></div>;
}

function JiraReference({ item }: { item: ReleaseNoteItem }) {
  return item.jira.url ? <a href={item.jira.url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()} className="inline-flex items-center gap-1 font-semibold text-[#a00028] hover:underline" aria-label={`Open ${item.jira.key} in Jira`}>{item.jira.key}<ExternalLink className="h-3.5 w-3.5" /></a> : <span className="font-semibold text-[#a00028]">{item.jira.key}</span>;
}

function ReleaseNoteDrawer({ item, release, onClose }: { item: ReleaseNoteItem; release: Release; onClose: () => void }) {
  return <div className="fixed inset-0 z-40 bg-stone-950/35" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><aside className="absolute inset-y-0 right-0 w-full max-w-xl overflow-y-auto border-l border-stone-300 bg-[#faf8f5] p-6 shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="release-note-title"><div className="flex items-start justify-between gap-3"><div><JiraReference item={item} /><h2 id="release-note-title" className="mt-2 text-2xl font-bold text-stone-900">{item.title}</h2></div><button type="button" onClick={onClose} aria-label="Close release note details" className="rounded-full p-2 text-stone-500 hover:bg-stone-200 focus:outline-none focus:ring-2 focus:ring-[#e0301e]"><X className="h-4 w-4" /></button></div>
    <div className="mt-4 flex flex-wrap gap-2"><Badge tone="purple">{CATEGORY_LABELS[item.category]}</Badge><Badge tone="success">{item.status}</Badge>{item.severity && <Badge tone={item.severity === "CRITICAL" || item.severity === "HIGH" ? "danger" : "warning"}>{item.severity}</Badge>}</div>
    <dl className="mt-5 divide-y divide-stone-200 rounded-2xl border border-stone-300 bg-white px-4 text-sm">{[["Epic", item.jira.epicKey ?? "—"], ["Component", item.component], ["Owner", item.owner ?? "—"], ["Issue type", item.jira.type ?? "—"], ["Validation", item.validationStatus ?? "—"]].map(([label, value]) => <div key={label} className="flex justify-between gap-4 py-3"><dt className="text-stone-500">{label}</dt><dd className="text-right font-semibold text-stone-900">{value}</dd></div>)}</dl>
    <section className="mt-6"><h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-stone-500">Description</h3><p className="mt-2 text-sm leading-6 text-stone-700">{item.description}</p></section>
    {item.resolution && <section className="mt-5"><h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-stone-500">Resolution</h3><p className="mt-2 text-sm leading-6 text-stone-700">{item.resolution}</p></section>}
    {item.businessImpact && <section className="mt-5"><h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-stone-500">Business impact</h3><p className="mt-2 text-sm leading-6 text-stone-700">{item.businessImpact}</p></section>}
    {item.workaround && <section className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4"><h3 className="text-sm font-semibold text-amber-950">Workaround</h3><p className="mt-2 text-sm text-amber-900">{item.workaround}</p><p className="mt-2 text-xs text-amber-800">Target fix: {item.targetFix}</p></section>}
    <div className="mt-6 rounded-xl border border-violet-200 bg-violet-50 p-4 text-sm text-violet-900"><strong>Related readiness:</strong> {release.readinessScore}% · {release.recommendation}</div>
    <div className="mt-6 flex flex-wrap gap-2">{item.jira.url && <a href={item.jira.url} target="_blank" rel="noreferrer" className="rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm font-semibold">Open in Jira</a>}<Link to={`/releases/${release.id}/readiness`} className="rounded-xl bg-[#a00028] px-3 py-2 text-sm font-semibold text-white">View Readiness</Link></div>
  </aside></div>;
}

export default function ReleaseNotesPage({ release }: { release: Release }) {
  const notes = release.releaseNotes;
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<"ALL" | ReleaseNoteCategory>("ALL");
  const [component, setComponent] = useState("ALL");
  const [selectedItem, setSelectedItem] = useState<ReleaseNoteItem | null>(null);
  const [copied, setCopied] = useState(false);

  const items = useMemo(() => notes?.items ?? [], [notes]);
  const components = useMemo(() => Array.from(new Set(items.map((item) => item.component))).sort(), [items]);
  const filteredItems = useMemo(() => {
    const term = search.trim().toLowerCase();
    return items.filter((item) => (category === "ALL" || item.category === category) && (component === "ALL" || item.component === component) && (!term || `${item.jira.key} ${item.title} ${item.description} ${item.component} ${item.jira.epicKey ?? ""}`.toLowerCase().includes(term)));
  }, [items, search, category, component]);

  if (!notes) return <section className="rounded-2xl border border-stone-300 bg-white p-8 text-center"><h2 className="text-xl font-bold text-stone-900">No release notes available</h2><p className="mt-2 text-stone-600">No release scope items have been associated with this release.</p></section>;

  const count = (value: ReleaseNoteCategory) => items.filter((item) => item.category === value).length;
  const copyLink = async () => { await navigator.clipboard?.writeText(window.location.href); setCopied(true); window.setTimeout(() => setCopied(false), 1200); };

  return <div className="space-y-6">
    <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm"><div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between"><div><p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">Release scope & traceability</p><h2 className="mt-2 text-2xl font-bold text-stone-900">Release Notes</h2><p className="mt-2 text-sm text-stone-600">{release.name} · v{release.version} · {release.environment}</p></div><div className="flex gap-2"><button type="button" onClick={() => window.print()} className="inline-flex items-center gap-2 rounded-xl border border-stone-300 px-3 py-2 text-sm font-semibold"><Download className="h-4 w-4" /> Export</button><button type="button" onClick={copyLink} className="inline-flex items-center gap-2 rounded-xl border border-stone-300 px-3 py-2 text-sm font-semibold"><Copy className="h-4 w-4" /> {copied ? "Copied" : "Copy Link"}</button></div></div></section>

    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6"><SummaryCard label="Features" value={count("FEATURE")} icon={FileText} /><SummaryCard label="Enhancements" value={count("ENHANCEMENT")} icon={Wrench} /><SummaryCard label="Bug fixes" value={count("BUG_FIX")} icon={ShieldCheck} /><SummaryCard label="Technical" value={count("TECHNICAL")} icon={Wrench} /><SummaryCard label="Known issues" value={count("KNOWN_ISSUE")} icon={FileText} /><SummaryCard label="Jira items" value={notes.jiraTraceability?.totalItems ?? items.length} icon={FileText} /></div>

    <div className="grid gap-6 xl:grid-cols-[1fr_320px]"><section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold text-stone-900">Release summary</h2><p className="mt-3 max-w-4xl text-sm leading-6 text-stone-700">{notes.summary}</p></section><aside className="rounded-2xl border border-violet-200 bg-violet-50 p-5"><p className="text-[11px] font-bold uppercase tracking-[0.16em] text-violet-700">Release readiness</p><p className="mt-2 text-2xl font-bold text-violet-950">{release.readinessScore}%</p><p className="mt-1 text-sm font-semibold text-violet-900">{release.recommendation}</p><p className="mt-2 text-sm text-violet-800">{release.blockers.length} blocker · {release.conditions.length} conditions</p><Link to={`/releases/${release.id}/readiness`} className="mt-4 inline-flex rounded-xl bg-[#a00028] px-3 py-2 text-sm font-semibold text-white">View Readiness</Link></aside></div>

    <section className="rounded-2xl border border-stone-300 bg-white p-4 shadow-sm"><div className="flex flex-col gap-3 xl:flex-row"><label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-stone-300 bg-stone-50 px-3 py-2"><Search className="h-4 w-4 text-stone-500" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by Jira key, title or component..." aria-label="Search release notes" className="w-full bg-transparent text-sm outline-none" /></label><div className="flex gap-2 overflow-x-auto pb-1">{(["ALL", "FEATURE", "ENHANCEMENT", "BUG_FIX", "TECHNICAL", "SECURITY", "KNOWN_ISSUE"] as const).map((value) => <button type="button" key={value} onClick={() => setCategory(value)} className={`whitespace-nowrap rounded-xl px-3 py-2 text-xs font-semibold ${category === value ? "bg-[#a00028] text-white" : "border border-stone-300 bg-white text-stone-700"}`}>{value === "ALL" ? "All" : CATEGORY_LABELS[value]}</button>)}</div><label className="rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 text-sm"><span className="sr-only">Filter by component</span><select value={component} onChange={(event) => setComponent(event.target.value)} className="bg-transparent outline-none"><option value="ALL">All components</option>{components.map((value) => <option key={value}>{value}</option>)}</select></label></div></section>

    <section><h2 className="text-xl font-bold text-stone-900">What's included</h2>{filteredItems.length ? <div className="mt-5 space-y-8">{CATEGORY_ORDER.map((group) => { const groupItems = filteredItems.filter((item) => item.category === group); if (!groupItems.length) return null; return <section key={group}><div className="flex items-center justify-between border-b border-stone-300 pb-2"><h3 className="text-sm font-bold uppercase tracking-[0.16em] text-stone-700">{CATEGORY_LABELS[group]}</h3><span className="text-xs text-stone-500">{groupItems.length}</span></div><div className="mt-3 grid gap-3 xl:grid-cols-2">{groupItems.map((item) => <button type="button" key={item.id} onClick={() => setSelectedItem(item)} className="rounded-2xl border border-stone-300 bg-white p-4 text-left shadow-sm transition hover:border-[#a00028] focus:outline-none focus:ring-2 focus:ring-[#e0301e]"><div className="flex items-start justify-between gap-3"><JiraReference item={item} /><div className="flex gap-2"><Badge tone="neutral">{item.component}</Badge>{item.severity && <Badge tone={item.severity === "CRITICAL" || item.severity === "HIGH" ? "danger" : "warning"}>{item.severity}</Badge>}</div></div><h4 className="mt-3 font-semibold text-stone-900">{item.title}</h4><p className="mt-2 line-clamp-3 text-sm leading-6 text-stone-600">{item.description}</p><div className="mt-3 flex items-center justify-between text-xs text-stone-500"><span>{item.jira.epicKey ?? item.jira.type}</span><span>{item.status}</span></div></button>)}</div></section>; })}</div> : <div className="mt-5 rounded-2xl border border-stone-300 bg-white p-8 text-center text-stone-600">No release-note items match your filters.</div>}</section>

    <div className="grid gap-6 xl:grid-cols-2"><section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold text-stone-900">Deployment notes</h2><dl className="mt-4 divide-y divide-stone-200 text-sm">{[["Deployment window", notes.deploymentNotes?.window], ["Environment", release.environment], ["Strategy", notes.deploymentNotes?.strategy], ["Expected downtime", notes.deploymentNotes?.expectedDowntime], ["Database migration", notes.deploymentNotes?.requiresDatabaseMigration ? "Required" : "Not required"], ["Migration head", notes.deploymentNotes?.migrationHeadHash], ["Post-deployment validation", notes.deploymentNotes?.requiresPostDeploymentValidation ? "Required" : "Not required"]].map(([label, value]) => <div key={label} className="flex justify-between gap-4 py-3"><dt className="text-stone-500">{label}</dt><dd className="text-right font-semibold text-stone-900">{value ?? "—"}</dd></div>)}</dl></section><section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold text-stone-900">Validation summary</h2><div className="mt-4 space-y-2">{notes.validationSummary?.map((item) => <div key={item.label} className="flex items-center justify-between rounded-xl bg-stone-50 p-3 text-sm"><div><strong className="text-stone-900">{item.label}</strong><p className="text-xs text-stone-500">{item.count ?? item.detail}</p></div><Badge tone={item.status === "PASS" ? "success" : item.status === "FAIL" ? "danger" : "warning"}>{item.status}</Badge></div>)}</div><div className="mt-4 flex gap-2"><Link to={`/releases/${release.id}/evidence`} className="rounded-xl border border-stone-300 px-3 py-2 text-sm font-semibold">View Evidence</Link><Link to={`/releases/${release.id}/hardening`} className="rounded-xl border border-stone-300 px-3 py-2 text-sm font-semibold">View Hardening</Link></div></section></div>

    <div className="grid gap-6 xl:grid-cols-2"><section className="rounded-2xl border border-stone-300 bg-white p-5"><h2 className="text-xl font-bold text-stone-900">Jira traceability</h2><p className="mt-3 text-3xl font-bold text-stone-900">{notes.jiraTraceability?.linkedItems} / {notes.jiraTraceability?.totalItems}</p><p className="mt-1 text-sm text-stone-600">Release items linked</p><div className="mt-4 space-y-2">{notes.jiraTraceability?.epicCoverage?.map((epic) => <div key={epic.epicKey} className="flex justify-between rounded-xl bg-stone-50 p-3 text-sm"><span><strong>{epic.epicKey}</strong> · {epic.epicTitle}</span><span>{epic.itemCount} items</span></div>)}</div></section><section className="rounded-2xl border border-stone-300 bg-white p-5"><h2 className="text-xl font-bold text-stone-900">Impact</h2><h3 className="mt-4 text-sm font-semibold text-stone-700">Impacted components</h3><div className="mt-2 flex flex-wrap gap-2">{notes.impactedComponents?.map((value) => <Badge key={value}>{value}</Badge>)}</div><h3 className="mt-5 text-sm font-semibold text-stone-700">Impacted users</h3><div className="mt-2 flex flex-wrap gap-2">{notes.impactedPersonas?.map((value) => <Badge key={value}>{value}</Badge>)}</div></section></div>
    {selectedItem && <ReleaseNoteDrawer item={selectedItem} release={release} onClose={() => setSelectedItem(null)} />}
  </div>;
}
