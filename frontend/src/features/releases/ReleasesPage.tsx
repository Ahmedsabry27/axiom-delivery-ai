import { useMemo, useState } from "react";
import { CalendarRange, CheckCircle2, Filter, RefreshCw, Rocket, Search, ShieldAlert } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useReleases } from "../../hooks/useReleases";
import type { ReleaseLifecycleStatus, ReleaseRecommendation } from "./types";

const lifecyclePalette: Record<ReleaseLifecycleStatus, string> = {
  PLANNING: "bg-stone-100 text-stone-700 border border-stone-200",
  "IN PROGRESS": "bg-sky-50 text-sky-700 border border-sky-200",
  VALIDATION: "bg-violet-50 text-violet-700 border border-violet-200",
  "READY FOR DECISION": "bg-amber-50 text-amber-800 border border-amber-200",
  APPROVED: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  SCHEDULED: "bg-blue-50 text-blue-700 border border-blue-200",
  DEPLOYING: "bg-orange-50 text-orange-700 border border-orange-200",
  DEPLOYED: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  BLOCKED: "bg-red-50 text-red-700 border border-red-200",
  CANCELLED: "bg-slate-100 text-slate-700 border border-slate-200",
};

const recommendationPalette: Record<ReleaseRecommendation, string> = {
  GO: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  "CONDITIONAL GO": "bg-violet-50 text-violet-700 border border-violet-200",
  "NO-GO": "bg-red-50 text-red-700 border border-red-200",
  "INSUFFICIENT EVIDENCE": "bg-amber-50 text-amber-800 border border-amber-200",
};

const formatShortDate = (value: string) =>
  new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short" }).format(new Date(value));

function StatusBadge({ children, tone = "default" }: { children: string; tone?: string }) {
  const palette = tone === "lifecycle" ? lifecyclePalette[children as ReleaseLifecycleStatus] ?? "bg-stone-100 text-stone-700 border border-stone-200" : tone === "recommendation" ? recommendationPalette[children as ReleaseRecommendation] ?? "bg-stone-100 text-stone-700 border border-stone-200" : "bg-stone-100 text-stone-700 border border-stone-200";
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ${palette}`}>{children}</span>;
}

function SummaryCard({ label, value, detail, icon: Icon }: { label: string; value: string; detail: string; icon: typeof Rocket }) {
  return (
    <div className="rounded-2xl border border-stone-300 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-stone-500">{label}</p>
          <p className="mt-3 text-3xl font-bold text-stone-900">{value}</p>
        </div>
        <div className="rounded-xl bg-[#faf8f5] p-2 text-[#a00028]"><Icon className="h-5 w-5" /></div>
      </div>
      <p className="mt-3 text-sm text-stone-600">{detail}</p>
    </div>
  );
}

export default function ReleasesPage() {
  const navigate = useNavigate();
  const releasesQuery = useReleases();
  const releases = releasesQuery.data ?? [];
  const [search, setSearch] = useState("");
  const [environment, setEnvironment] = useState("All");
  const [status, setStatus] = useState("All");
  const [releaseType, setReleaseType] = useState("All");
  const [owner, setOwner] = useState("All");
  const [targetDate, setTargetDate] = useState("");
  const [sort, setSort] = useState("targetDate");

  const filteredReleases = useMemo(() => {
    const term = search.trim().toLowerCase();
    const next = releases.filter((release) => {
      const matchesSearch = !term || `${release.name} ${release.id} ${release.releaseOwner}`.toLowerCase().includes(term);
      const matchesEnvironment = environment === "All" || release.environment === environment;
      const matchesStatus = status === "All" || release.lifecycle === status || release.recommendation === status;
      const matchesType = releaseType === "All" || release.releaseType === releaseType;
      const matchesOwner = owner === "All" || release.releaseOwner === owner;
      const matchesTargetDate = !targetDate || release.targetDate.slice(0, 10) <= targetDate;
      return matchesSearch && matchesEnvironment && matchesStatus && matchesType && matchesOwner && matchesTargetDate;
    });

    return [...next].sort((left, right) => {
      if (sort === "readiness") return right.readinessScore - left.readinessScore;
      if (sort === "risk") return (right.blockers.length > 0 ? 1 : 0) - (left.blockers.length > 0 ? 1 : 0) || new Date(left.targetDate).getTime() - new Date(right.targetDate).getTime();
      return new Date(left.targetDate).getTime() - new Date(right.targetDate).getTime();
    });
  }, [releases, search, environment, status, releaseType, owner, targetDate, sort]);

  const summary = {
    active: releases.length,
    upcoming: releases.filter((release) => release.lifecycle !== "DEPLOYED" && release.lifecycle !== "CANCELLED").length,
    atRisk: releases.filter((release) => release.blockers.length > 0 || release.recommendation === "NO-GO").length,
    readyForDecision: releases.filter((release) => release.lifecycle === "READY FOR DECISION" || release.recommendation === "CONDITIONAL GO").length,
  };

  return (
    <main className="min-h-full bg-[#faf8f5] p-5 text-[#202020] md:p-8">
      <header className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#a00028]">Delivery governance</p>
          <h1 className="mt-2 font-display text-4xl font-bold text-stone-900">Releases</h1>
          <p className="mt-2 max-w-2xl text-sm text-stone-600">Plan, govern and monitor releases from preparation through production approval.</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button type="button" className="inline-flex items-center gap-2 rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700"><RefreshCw className="h-4 w-4" /> Refresh</button>
          <button type="button" className="rounded-xl bg-[#a00028] px-4 py-2.5 text-sm font-semibold text-white">New Release</button>
        </div>
      </header>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="Active releases" value={String(summary.active)} detail="Current portfolio view" icon={Rocket} />
        <SummaryCard label="Upcoming" value={String(summary.upcoming)} detail="Releases yet to be deployed" icon={CalendarRange} />
        <SummaryCard label="At risk" value={String(summary.atRisk)} detail="Requires immediate attention" icon={ShieldAlert} />
        <SummaryCard label="Ready for decision" value={String(summary.readyForDecision)} detail="Decision-ready release set" icon={CheckCircle2} />
      </div>

      <div className="mt-6 rounded-2xl border border-stone-300 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-1 flex-col gap-3 md:flex-row">
            <label className="flex min-w-[220px] flex-1 items-center gap-2 rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 text-sm text-stone-600">
              <Search className="h-4 w-4 text-stone-500" />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by release, ID or owner" className="w-full bg-transparent outline-none placeholder:text-stone-400" aria-label="Search releases" />
            </label>
            <div className="flex flex-wrap gap-3">
              <label className="flex items-center gap-2 rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 text-sm text-stone-600">
                <Filter className="h-4 w-4 text-stone-500" />
                <select value={environment} onChange={(event) => setEnvironment(event.target.value)} className="bg-transparent outline-none">
                  <option value="All">Environment</option>
                  <option value="PROD">PROD</option>
                  <option value="UAT">UAT</option>
                  <option value="STAGING">STAGING</option>
                  <option value="DEV">DEV</option>
                </select>
              </label>
              <label className="flex items-center gap-2 rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 text-sm text-stone-600">
                <Filter className="h-4 w-4 text-stone-500" />
                <select value={releaseType} onChange={(event) => setReleaseType(event.target.value)} className="bg-transparent outline-none" aria-label="Release type">
                  <option value="All">Release type</option><option value="Major Release">Major release</option><option value="Minor Release">Minor release</option><option value="Maintenance Release">Maintenance release</option>
                </select>
              </label>
              <label className="flex items-center gap-2 rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 text-sm text-stone-600">
                <Filter className="h-4 w-4 text-stone-500" />
                <select value={owner} onChange={(event) => setOwner(event.target.value)} className="bg-transparent outline-none" aria-label="Release owner">
                  <option value="All">Release owner</option>{Array.from(new Set(releases.map((release) => release.releaseOwner))).map((name) => <option key={name} value={name}>{name}</option>)}
                </select>
              </label>
              <label className="flex items-center gap-2 rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 text-sm text-stone-600">
                <CalendarRange className="h-4 w-4 text-stone-500" /><span className="sr-only">Target date through</span><input type="date" value={targetDate} onChange={(event) => setTargetDate(event.target.value)} className="bg-transparent outline-none" aria-label="Target date through" />
              </label>
              <label className="flex items-center gap-2 rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 text-sm text-stone-600">
                <Filter className="h-4 w-4 text-stone-500" />
                <select value={status} onChange={(event) => setStatus(event.target.value)} className="bg-transparent outline-none">
                  <option value="All">Status</option>
                  <option value="READY FOR DECISION">Ready for decision</option>
                  <option value="VALIDATION">Validation</option>
                  <option value="PLANNING">Planning</option>
                  <option value="DEPLOYED">Deployed</option>
                  <option value="CONDITIONAL GO">Conditional Go</option>
                  <option value="INSUFFICIENT EVIDENCE">Insufficient evidence</option>
                </select>
              </label>
              <label className="flex items-center gap-2 rounded-xl border border-stone-300 bg-stone-50 px-3 py-2 text-sm text-stone-600">
                <Filter className="h-4 w-4 text-stone-500" />
                <select value={sort} onChange={(event) => setSort(event.target.value)} className="bg-transparent outline-none">
                  <option value="targetDate">Target date</option>
                  <option value="readiness">Readiness</option>
                  <option value="risk">Risk</option>
                </select>
              </label>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded-2xl border border-stone-300 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm text-stone-700">
            <thead className="bg-stone-50 text-[11px] font-bold uppercase tracking-[0.14em] text-stone-500">
              <tr>
                <th className="px-4 py-3">Release</th>
                <th className="px-4 py-3">Version</th>
                <th className="px-4 py-3">Environment</th>
                <th className="px-4 py-3">Target Date</th>
                <th className="px-4 py-3">Owner</th>
                <th className="px-4 py-3">Lifecycle</th>
                <th className="px-4 py-3">Readiness</th>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Blockers</th>
                <th className="px-4 py-3">Evidence</th>
                <th className="px-4 py-3">Decision</th>
                <th className="px-4 py-3">Updated</th>
              </tr>
            </thead>
            <tbody>
              {releasesQuery.isLoading ? <tr><td colSpan={12} className="px-4 py-8 text-center text-stone-600">Loading releases…</td></tr> : releasesQuery.isError ? <tr><td colSpan={12} className="px-4 py-8 text-center text-red-700">Unable to load releases from the delivery API.</td></tr> : filteredReleases.length ? filteredReleases.map((release) => (
                <tr key={release.id} className="cursor-pointer border-t border-stone-200 hover:bg-stone-50" onClick={() => navigate(`/releases/${release.id}`)}>
                  <td className="px-4 py-3">
                    <div>
                      <p className="font-semibold text-stone-900">{release.name}</p>
                      <p className="mt-1 text-xs text-stone-500">{release.releaseId}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-medium text-stone-700">v{release.version}</td>
                  <td className="px-4 py-3 text-stone-700">{release.environment}</td>
                  <td className="px-4 py-3">{formatShortDate(release.targetDate)}</td>
                  <td className="px-4 py-3">{release.releaseOwner}</td>
                  <td className="px-4 py-3"><StatusBadge tone="lifecycle">{release.lifecycle}</StatusBadge></td>
                  <td className="px-4 py-3"><StatusBadge tone="recommendation">{release.recommendation}</StatusBadge></td>
                  <td className="px-4 py-3 font-semibold text-stone-900">{release.readinessScore}%</td>
                  <td className="px-4 py-3">{release.blockers.length}</td>
                  <td className="px-4 py-3">{release.evidenceSummary.verified} / {release.evidenceSummary.total}</td>
                  <td className="px-4 py-3">{release.currentDecision?.decision ?? "Pending"}</td>
                  <td className="px-4 py-3 text-stone-500">{new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(release.updatedAt))}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={12} className="px-4 py-8 text-center text-stone-600">No releases match your filters.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
