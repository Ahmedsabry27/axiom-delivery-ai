import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  Clock3,
  FileCheck2,
  Gauge,
  RefreshCw,
  Rocket,
  ShieldCheck,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { mockReleaseReadinessData } from "./data/mockReleaseReadiness";
import { calculateReadiness, getRecommendation } from "./utils/calculateReadiness";
import type {
  EvidenceItem,
  ReadinessCriterion,
  ReleaseCondition,
  ReleaseDecisionHistoryEntry,
  ReleaseRecord,
  TraceSpan,
} from "./types";

const statusStyles: Record<string, string> = {
  PASSED: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  FAILED: "bg-rose-50 text-rose-700 border border-rose-200",
  PENDING: "bg-amber-50 text-amber-800 border border-amber-200",
  "MISSING EVIDENCE": "bg-orange-50 text-orange-700 border border-orange-200",
  WAIVED: "bg-slate-100 text-slate-700 border border-slate-200",
  CONDITIONAL: "bg-violet-50 text-violet-700 border border-violet-200",
  PASS: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  FAIL: "bg-rose-50 text-rose-700 border border-rose-200",
  "Decision deferred": "bg-stone-200 text-stone-700 border border-stone-200",
  GO: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  "CONDITIONAL GO": "bg-violet-50 text-violet-700 border border-violet-200",
  "NO-GO": "bg-rose-50 text-rose-700 border border-rose-200",
  "INSUFFICIENT EVIDENCE": "bg-amber-50 text-amber-800 border border-amber-200",
};

const formatDate = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(date);
};

const formatDetailedDate = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
};

const toDecisionLabel = (decision: string) => decision === "Decision deferred" ? "Decision deferred" : decision;

function StatusBadge({ children, tone = "default" }: { children: React.ReactNode; tone?: string }) {
  const toneClass = statusStyles[tone] ?? statusStyles.PASSED;
  return <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ${toneClass}`}>{children}</span>;
}

function MetricCard({ label, value, detail, icon: Icon, accent = "text-[#a00028]" }: { label: string; value: string; detail: string; icon: typeof ShieldCheck; accent?: string }) {
  return (
    <div className="rounded-2xl border border-stone-300 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">{label}</p>
          <p className="mt-3 text-3xl font-bold text-stone-900">{value}</p>
        </div>
        <div className={`rounded-xl bg-[#faf8f5] p-2 ${accent}`}><Icon className="h-5 w-5" /></div>
      </div>
      <p className="mt-3 text-sm text-stone-600">{detail}</p>
    </div>
  );
}

function ReadinessCriteriaGrid({ criteria, onSelect }: { criteria: ReadinessCriterion[]; onSelect: (criterion: ReadinessCriterion) => void }) {
  return (
    <div className="grid gap-3 xl:grid-cols-2">
      {criteria.map((criterion) => (
        <button
          key={criterion.id}
          type="button"
          onClick={() => onSelect(criterion)}
          className="flex w-full flex-col rounded-2xl border border-stone-300 bg-white p-4 text-left transition hover:border-[#a00028] hover:bg-stone-50 focus:outline-none focus:ring-2 focus:ring-[#e0301e]"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold text-stone-900">{criterion.name}</p>
              <p className="mt-1 text-sm text-stone-600">{criterion.note}</p>
            </div>
            <StatusBadge tone={criterion.status}>{criterion.status}</StatusBadge>
          </div>

          <div className="mt-4 grid gap-2 text-xs text-stone-600 sm:grid-cols-2">
            <div>
              <span className="block text-stone-500">Owner</span>
              <span className="mt-1 block font-medium text-stone-800">{criterion.owner}</span>
            </div>
            <div>
              <span className="block text-stone-500">Updated</span>
              <span className="mt-1 block font-medium text-stone-800">{formatDate(criterion.lastUpdated)}</span>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between gap-3 border-t border-stone-200 pt-3 text-xs text-stone-600">
            <div className="flex items-center gap-2">
              <span className={`rounded-full px-2 py-1 font-medium ${criterion.mandatory ? "bg-rose-50 text-rose-700" : "bg-stone-100 text-stone-700"}`}>
                {criterion.mandatory ? "Mandatory" : "Optional"}
              </span>
              {criterion.blocking ? <span className="text-rose-600">Blocking</span> : <span>Non-blocking</span>}
            </div>
            <span className="inline-flex items-center gap-1 font-medium text-[#a00028]">
              Details <ChevronRight className="h-3.5 w-3.5" />
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}

function EvidenceModal({ evidence, onClose }: { evidence: EvidenceItem | null; onClose: () => void }) {
  if (!evidence) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/45 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-lg rounded-2xl border border-stone-300 bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#a00028]">Evidence</p>
            <h3 className="mt-2 text-xl font-bold text-stone-900">{evidence.title}</h3>
          </div>
          <button type="button" onClick={onClose} aria-label="Close evidence panel" className="rounded-full p-2 text-stone-500 hover:bg-stone-100"><X className="h-4 w-4" /></button>
        </div>

        <div className="mt-5 grid gap-3 text-sm text-stone-700 sm:grid-cols-2">
          <div><span className="text-stone-500">Type</span><p className="mt-1 font-medium text-stone-900">{evidence.type}</p></div>
          <div><span className="text-stone-500">Owner</span><p className="mt-1 font-medium text-stone-900">{evidence.owner}</p></div>
          <div><span className="text-stone-500">Source</span><p className="mt-1 font-medium text-stone-900">{evidence.source}</p></div>
          <div><span className="text-stone-500">Status</span><p className="mt-1 font-medium text-stone-900">{evidence.status}</p></div>
        </div>

        <p className="mt-5 text-sm text-stone-600">Recorded: {formatDetailedDate(evidence.recorded)}</p>
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-semibold text-stone-700">Close</button>
          <button type="button" className="rounded-xl bg-[#a00028] px-4 py-2 text-sm font-semibold text-white">Open source</button>
        </div>
      </div>
    </div>
  );
}

function CriterionDrawer({ criterion, onClose, onOpenEvidence }: { criterion: ReadinessCriterion | null; onClose: () => void; onOpenEvidence: (evidence: EvidenceItem) => void }) {
  if (!criterion) return null;

  const evidenceItems: EvidenceItem[] = [
    { id: "related-1", title: "Penetration Test Report", type: "Security", source: "Jira", owner: "InfoSec", recorded: "2026-10-03T16:10:00.000Z", status: "Verified" },
    { id: "related-2", title: "Security Review AX-184", type: "Security", source: "Jira", owner: "InfoSec", recorded: "2026-10-02T11:42:00.000Z", status: "Pending" },
    { id: "related-3", title: "Vulnerability Scan", type: "Security", source: "Azure Defender", owner: "InfoSec", recorded: "2026-10-03T08:00:00.000Z", status: "Verified" },
  ];

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-full max-w-xl border-l border-stone-300 bg-[#faf8f5] p-6 shadow-2xl" role="dialog" aria-modal="true" aria-label={`${criterion.name} details`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#a00028]">Criterion</p>
          <h3 className="mt-2 text-2xl font-bold text-stone-900">{criterion.name}</h3>
        </div>
        <button type="button" onClick={onClose} aria-label="Close criterion drawer" className="rounded-full p-2 text-stone-500 hover:bg-stone-200"><X className="h-4 w-4" /></button>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <StatusBadge tone={criterion.status}>{criterion.status}</StatusBadge>
        {criterion.blocking && <StatusBadge tone="FAILED">Blocking criterion</StatusBadge>}
      </div>

      <div className="mt-6 rounded-2xl border border-stone-300 bg-white p-4">
        <div className="grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <span className="text-stone-500">Owner</span>
            <p className="mt-1 font-semibold text-stone-900">{criterion.owner}</p>
          </div>
          <div>
            <span className="text-stone-500">Last updated</span>
            <p className="mt-1 font-semibold text-stone-900">{formatDetailedDate(criterion.lastUpdated)}</p>
          </div>
        </div>
      </div>

      <section className="mt-6">
        <h4 className="text-sm font-semibold uppercase tracking-[0.12em] text-stone-500">Requirement</h4>
        <p className="mt-2 text-sm leading-6 text-stone-700">{criterion.note}</p>
      </section>

      <section className="mt-6">
        <h4 className="text-sm font-semibold uppercase tracking-[0.12em] text-stone-500">Evidence</h4>
        <p className="mt-2 text-sm text-stone-700">{criterion.evidenceLabel ?? "No approval evidence uploaded."}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" className="rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700">View Evidence</button>
          <button type="button" className="rounded-xl bg-[#a00028] px-3 py-2 text-sm font-semibold text-white">Add Evidence</button>
          <button type="button" className="rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700">Request Review</button>
        </div>
      </section>

      <section className="mt-6">
        <h4 className="text-sm font-semibold uppercase tracking-[0.12em] text-stone-500">Related evidence</h4>
        <ul className="mt-3 space-y-2">
          {evidenceItems.map((item) => (
            <li key={item.id}>
              <button type="button" onClick={() => onOpenEvidence(item)} className="flex w-full items-center justify-between rounded-xl border border-stone-300 bg-white px-3 py-2 text-left text-sm text-stone-700 hover:bg-stone-50">
                <span>{item.title}</span>
                <ChevronRight className="h-4 w-4 text-stone-400" />
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-6">
        <h4 className="text-sm font-semibold uppercase tracking-[0.12em] text-stone-500">Dependencies</h4>
        <p className="mt-2 text-sm text-stone-700">• AX-610 regression completion</p>
      </section>

      <section className="mt-6">
        <h4 className="text-sm font-semibold uppercase tracking-[0.12em] text-stone-500">History</h4>
        <ul className="mt-3 space-y-2 text-sm text-stone-700">
          <li>03 Oct 16:10 — Review requested</li>
          <li>02 Oct 11:42 — Security evidence submitted</li>
        </ul>
      </section>
    </div>
  );
}

function TraceSpanDrawer({ span, traceId, onClose }: { span: TraceSpan | null; traceId: string; onClose: () => void }) {
  if (!span) return null;
  return (
    <div className="fixed inset-0 z-40 bg-stone-950/30" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <aside className="absolute inset-y-0 right-0 w-full max-w-md overflow-y-auto border-l border-stone-300 bg-[#faf8f5] p-6 shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="trace-stage-title">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#a00028]">Sanitized trace stage</p>
            <h3 id="trace-stage-title" className="mt-2 text-2xl font-bold text-stone-900">{span.stage}</h3>
          </div>
          <button type="button" onClick={onClose} aria-label="Close trace details" className="rounded-full p-2 text-stone-500 hover:bg-stone-200 focus:outline-none focus:ring-2 focus:ring-[#e0301e]"><X className="h-4 w-4" /></button>
        </div>
        <dl className="mt-6 divide-y divide-stone-200 rounded-2xl border border-stone-300 bg-white px-4 text-sm">
          {[["Trace ID", traceId], ["Span ID", span.id], ["Identifier", span.identifier], ["Status", span.status], ["Duration", `${span.durationMs} ms`], ["Timestamp", formatDetailedDate(span.timestamp)], ["Metadata", span.metadata ?? "No sensitive metadata retained"]].map(([label, value]) => (
            <div key={label} className="flex items-start justify-between gap-4 py-3"><dt className="text-stone-500">{label}</dt><dd className="text-right font-medium text-stone-900">{value}</dd></div>
          ))}
        </dl>
        <p className="mt-5 text-xs leading-5 text-stone-500">Inputs, outputs, credentials, and sensitive payloads are intentionally excluded from this view.</p>
      </aside>
    </div>
  );
}

function RecordDecisionModal({ open, onClose, currentDecision, onConfirm, selectedRelease }: { open: boolean; currentDecision: ReleaseDecisionHistoryEntry | null; onClose: () => void; onConfirm: (decision: string, rationale: string, conditions: string) => void; selectedRelease: ReleaseRecord }) {
  const [selection, setSelection] = useState(currentDecision?.decision ?? "CONDITIONAL GO");
  const [rationale, setRationale] = useState(currentDecision?.rationale ?? "");
  const [conditions, setConditions] = useState(currentDecision?.conditions?.join("\n") ?? selectedRelease.conditions.map((entry) => entry.summary).join("\n"));

  if (!open) return null;

  const decisionRequiresCondition = selection === "CONDITIONAL GO";
  const decisionRequiresRationale = selection === "NO-GO" || selection === "Decision deferred";

  const submit = () => {
    if (decisionRequiresCondition && !conditions.trim()) return;
    if (decisionRequiresRationale && !rationale.trim()) return;
    onConfirm(selection, rationale, conditions);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/45 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-xl rounded-2xl border border-stone-300 bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#a00028]">Decision capture</p>
            <h3 className="mt-2 text-2xl font-bold text-stone-900">Record release decision</h3>
          </div>
          <button type="button" aria-label="Close decision dialog" onClick={onClose} className="rounded-full p-2 text-stone-500 hover:bg-stone-100"><X className="h-4 w-4" /></button>
        </div>

        <div className="mt-5 rounded-2xl border border-stone-200 bg-[#faf8f5] p-4 text-sm text-stone-700">
          <p className="font-semibold text-stone-900">AI Recommendation</p>
          <p className="mt-1">{selectedRelease.recommendation.level}</p>
        </div>

        <div className="mt-6 space-y-3">
          {(["GO", "CONDITIONAL GO", "NO-GO", "Decision deferred"] as const).map((decision) => (
            <label key={decision} className="flex items-center gap-3 rounded-xl border border-stone-300 bg-white p-3 text-sm text-stone-700">
              <input type="radio" name="decision" checked={selection === decision} onChange={() => setSelection(decision)} />
              <span>{decision}</span>
            </label>
          ))}
        </div>

        <div className="mt-6 space-y-4">
          <label className="block text-sm text-stone-700">
            Decision rationale
            <textarea value={rationale} onChange={(event) => setRationale(event.target.value)} rows={4} className="mt-2 w-full rounded-xl border border-stone-300 bg-stone-50 p-3 text-stone-900" placeholder="Summarise the final decision rationale." />
          </label>

          <label className="block text-sm text-stone-700">
            Conditions
            <textarea value={conditions} onChange={(event) => setConditions(event.target.value)} rows={4} className="mt-2 w-full rounded-xl border border-stone-300 bg-stone-50 p-3 text-stone-900" placeholder="Document any required conditions or exceptions." />
          </label>
        </div>

        <div className="mt-6 rounded-2xl border border-stone-200 bg-stone-50 p-4 text-sm text-stone-700">
          You are recording a production release decision. This action will be captured in the audit history.
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="rounded-xl border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-700">Cancel</button>
          <button type="button" onClick={submit} className="rounded-xl bg-[#a00028] px-4 py-2 text-sm font-semibold text-white">Record decision</button>
        </div>
      </div>
    </div>
  );
}

function ReleaseReadinessTab({ selectedRelease, onSelectCriterion, onOpenEvidence }: { selectedRelease: ReleaseRecord; onSelectCriterion: (criterion: ReadinessCriterion) => void; onOpenEvidence: (evidence: EvidenceItem) => void }) {
  const readiness = calculateReadiness(selectedRelease.criteria);
  const recommendation = getRecommendation(selectedRelease.criteria, readiness.percentage);
  const donutData = [
    { name: "Passed", value: readiness.passed },
    { name: "Pending", value: Math.max(1, readiness.total - readiness.passed) },
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Readiness score" value={`${readiness.percentage}%`} detail={`${readiness.passed} / ${readiness.total} criteria passed`} icon={Gauge} accent="text-[#a00028]" />
        <MetricCard label="AI Recommendation" value={recommendation.level} detail={`${selectedRelease.conditions.length} conditions`} icon={Sparkles} accent="text-violet-700" />
        <MetricCard label="Open blockers" value={String(selectedRelease.blockers.length)} detail={`${selectedRelease.blockers.filter((item) => item.severity === "Critical").length} critical`} icon={AlertTriangle} accent="text-rose-600" />
        <MetricCard label="Evidence coverage" value={`${selectedRelease.recommendation.evidenceCoverage}%`} detail={`${selectedRelease.recommendation.evidenceVerified} / ${selectedRelease.recommendation.evidenceTotal} verified`} icon={FileCheck2} accent="text-emerald-700" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_1.2fr_0.9fr]">
        <section className="rounded-2xl border border-stone-300 bg-white p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">Release readiness</p>
              <h2 className="mt-2 text-2xl font-bold text-stone-900">{readiness.percentage}%</h2>
            </div>
            <div className="h-20 w-20">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={donutData} dataKey="value" innerRadius={20} outerRadius={34} startAngle={90} endAngle={-270} paddingAngle={2} stroke="transparent">
                    {["#a00028", "#e7e5e4"].map((color, index) => (<Cell key={color} fill={color} opacity={index === 0 ? 1 : 0.9} />))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
          <p className="mt-4 text-sm text-stone-600">{readiness.passed} / {readiness.total} criteria passed</p>
          <div className="mt-4 grid gap-3 text-sm text-stone-700 sm:grid-cols-2">
            <div className="rounded-xl bg-stone-50 p-3"><span className="block text-stone-500">Passed</span><strong className="mt-1 block text-stone-900">{readiness.passed}</strong></div>
            <div className="rounded-xl bg-stone-50 p-3"><span className="block text-stone-500">Missing evidence</span><strong className="mt-1 block text-stone-900">{selectedRelease.recommendation.evidenceTotal - selectedRelease.recommendation.evidenceVerified}</strong></div>
            <div className="rounded-xl bg-stone-50 p-3"><span className="block text-stone-500">Blocking criteria</span><strong className="mt-1 block text-stone-900">{readiness.blocked}</strong></div>
            <div className="rounded-xl bg-stone-50 p-3"><span className="block text-stone-500">Conditions</span><strong className="mt-1 block text-stone-900">{readiness.conditionCount}</strong></div>
          </div>
        </section>

        <section className="rounded-2xl border border-stone-300 bg-white p-5">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">AI Recommendation</p>
          <div className="mt-3 flex items-center gap-2">
            <StatusBadge tone={recommendation.level}>{recommendation.level}</StatusBadge>
            <span className="text-sm text-stone-500">AI recommendation</span>
          </div>
          <p className="mt-4 text-base font-medium text-stone-900">{recommendation.summary}</p>
          <p className="mt-4 text-sm text-stone-600">The system provides a recommendation based on available evidence. The final release decision must be made by an authorized human decision owner.</p>
          <div className="mt-5 rounded-xl border border-stone-200 bg-stone-50 p-3 text-sm text-stone-700">
            <div className="flex items-center justify-between"><span>Evidence confidence</span><strong>{selectedRelease.recommendation.evidenceConfidence}</strong></div>
            <div className="mt-2 flex items-center justify-between"><span>Evidence coverage</span><strong>{selectedRelease.recommendation.evidenceCoverage}%</strong></div>
            <div className="mt-2 flex items-center justify-between"><span>Last evaluated</span><strong>{formatDetailedDate(selectedRelease.recommendation.evaluatedAt)}</strong></div>
          </div>
          <button type="button" className="mt-5 inline-flex items-center gap-2 rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700"><FileCheck2 className="h-4 w-4" /> View recommendation evidence</button>
        </section>

        <section className="rounded-2xl border border-stone-300 bg-white p-5">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">Human decision</p>
          <div className="mt-3 flex items-center gap-2">
            {selectedRelease.currentDecision ? <StatusBadge tone={selectedRelease.currentDecision.decision}>{selectedRelease.currentDecision.decision}</StatusBadge> : <StatusBadge tone="PENDING">PENDING</StatusBadge>}
          </div>
          <p className="mt-3 text-sm text-stone-700">Decision owner: {selectedRelease.decisionOwner}</p>
          <p className="mt-2 text-sm text-stone-600">Final deployment authority remains with the authorized human decision owner.</p>
        </section>
      </div>

      <section className="rounded-2xl border border-stone-300 bg-white p-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-bold text-stone-900">Readiness criteria</h2>
          <span className="text-sm text-stone-500">{selectedRelease.criteria.length} criteria</span>
        </div>
        <div className="mt-5">
          <ReadinessCriteriaGrid criteria={selectedRelease.criteria} onSelect={onSelectCriterion} />
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-2xl border border-stone-300 bg-white p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-xl font-bold text-stone-900">Open blockers</h2>
            <span className="rounded-full bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700">{selectedRelease.blockers.length}</span>
          </div>
          <div className="mt-4 space-y-3">
            {selectedRelease.blockers.map((blocker) => (
              <article key={blocker.id} className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-stone-500">{blocker.id}</p>
                    <h3 className="mt-2 font-semibold text-stone-900">{blocker.title}</h3>
                  </div>
                  <StatusBadge tone={blocker.severity}>{blocker.severity}</StatusBadge>
                </div>
                <div className="mt-3 grid gap-2 text-sm text-stone-700 sm:grid-cols-2">
                  <div><span className="text-stone-500">Owner</span><p className="mt-1 font-medium text-stone-900">{blocker.owner}</p></div>
                  <div><span className="text-stone-500">Due</span><p className="mt-1 font-medium text-stone-900">{blocker.due}</p></div>
                </div>
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-stone-600">
                  <span>{blocker.linkedCriterion}</span>
                  <button type="button" onClick={() => onOpenEvidence({ id: blocker.id, title: blocker.title, type: "Blocker evidence", source: "Release system", owner: blocker.owner, recorded: new Date().toISOString(), status: "Pending" })} className="inline-flex items-center gap-1 font-medium text-[#a00028]">
                    View action <ArrowRight className="h-3 w-3" />
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-stone-300 bg-white p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-xl font-bold text-stone-900">Conditions & exceptions</h2>
            <span className="rounded-full bg-stone-100 px-2.5 py-1 text-xs font-semibold text-stone-700">{selectedRelease.conditions.length + selectedRelease.exceptions.length}</span>
          </div>

          <div className="mt-5 space-y-4">
            <div>
              <p className="text-sm font-semibold text-stone-900">Conditions</p>
              <div className="mt-3 space-y-3">
                {selectedRelease.conditions.map((condition: ReleaseCondition) => (
                  <div key={condition.id} className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                    <p className="font-medium">{condition.summary}</p>
                    <div className="mt-2 flex items-center justify-between gap-3 text-xs">
                      <span>Owner: {condition.owner}</span>
                      <span>Due: {formatDate(condition.due)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <p className="text-sm font-semibold text-stone-900">Approved exceptions</p>
              <div className="mt-3 space-y-3">
                {selectedRelease.exceptions.length ? selectedRelease.exceptions.map((exception: ReleaseCondition) => (
                  <div key={exception.id} className="rounded-xl border border-violet-200 bg-violet-50 p-3 text-sm text-violet-800">
                    <p className="font-medium">{exception.summary}</p>
                    <div className="mt-2 flex items-center justify-between gap-3 text-xs">
                      <span>Approved by: {exception.approvedBy}</span>
                      <span>Valid until: {formatDate(exception.validUntil ?? exception.due)}</span>
                    </div>
                  </div>
                )) : <p className="text-sm text-stone-500">No approved exceptions recorded.</p>}
              </div>
            </div>
          </div>
        </section>
      </div>

      <section className="rounded-2xl border border-stone-300 bg-white p-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-bold text-stone-900">Go / No-Go decision</h2>
          <StatusBadge tone={selectedRelease.recommendation.level}>{selectedRelease.recommendation.level}</StatusBadge>
        </div>
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
            <p className="text-sm font-semibold text-stone-900">AI recommendation</p>
            <p className="mt-2 text-2xl font-bold text-stone-900">{selectedRelease.recommendation.level}</p>
            <p className="mt-2 text-sm text-stone-600">{selectedRelease.recommendation.summary}</p>
          </div>
          <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
            <p className="text-sm font-semibold text-stone-900">Human decision</p>
            <p className="mt-2 text-2xl font-bold text-stone-900">{selectedRelease.currentDecision?.decision ?? "PENDING"}</p>
            <p className="mt-2 text-sm text-stone-600">Decision owner: {selectedRelease.decisionOwner}</p>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-stone-300 bg-white p-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-bold text-stone-900">Decision history</h2>
        </div>
        <div className="mt-5 space-y-4">
          {selectedRelease.decisionHistory.map((entry) => (
            <div key={entry.id} className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-stone-500">{formatDetailedDate(entry.timestamp)}</p>
                  <p className="mt-1 text-lg font-semibold text-stone-900">{toDecisionLabel(entry.decision)}</p>
                </div>
                <div className="text-right text-sm text-stone-600">
                  <p>{entry.owner}</p>
                  <p>{entry.role}</p>
                </div>
              </div>
              <p className="mt-3 text-sm text-stone-700">{entry.rationale}</p>
              {entry.conditions && entry.conditions.length > 0 && (
                <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-stone-600">
                  {entry.conditions.map((condition) => <li key={`${entry.id}-${condition}`}>{condition}</li>)}
                </ul>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function HardeningTab({ selectedRelease, onSelectSpan }: { selectedRelease: ReleaseRecord; onSelectSpan: (span: TraceSpan) => void }) {
  const { hardening } = selectedRelease;
  const tracePasses = hardening.trace.spans.filter((span) => span.status === "PASS").length;
  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-stone-300 bg-white p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#a00028]">MVP hardening status</p>
            <h2 className="mt-2 text-2xl font-bold text-stone-900">READY</h2>
          </div>
          <StatusBadge tone="GO">PASS</StatusBadge>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-6">
          <MetricCard label="Tracing" value="PASS" detail={`${tracePasses} / ${hardening.trace.spans.length} spans successful`} icon={Target} accent="text-[#a00028]" />
          <MetricCard label="Authorization" value={`${hardening.authorization.passed}/${hardening.authorization.testsExecuted}`} detail="Role and tenancy gates are passing" icon={ShieldCheck} accent="text-emerald-700" />
          <MetricCard label="AI monitoring" value="PASS" detail={`${hardening.monitoring.successRate}% success rate`} icon={CheckCircle2} accent="text-violet-700" />
          <MetricCard label="AI evaluation" value={hardening.quality.overallStatus} detail={hardening.quality.thresholdMet} icon={BrainCircuit} accent="text-violet-700" />
          <MetricCard label="Security review" value={hardening.security.overallStatus} detail="0 critical · 0 high" icon={ShieldCheck} accent="text-emerald-700" />
          <MetricCard label="Regression journey" value={hardening.regression.status} detail={`${hardening.regression.steps.filter((step) => step.status === "done").length} / ${hardening.regression.steps.length} steps`} icon={CheckCircle2} accent="text-emerald-700" />
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-2xl border border-stone-300 bg-white p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">AX-605</p>
              <h3 className="mt-2 text-xl font-bold text-stone-900">End-to-end tracing</h3>
            </div>
            <StatusBadge tone="GO">PASS</StatusBadge>
          </div>
          <div className="mt-5 rounded-2xl border border-stone-200 bg-stone-50 p-4">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-stone-500">Trace ID</p>
            <p className="mt-2 font-mono text-sm text-stone-900">{hardening.trace.id}</p>
          </div>
          <div className="mt-5 space-y-3">
            {hardening.trace.spans.map((span) => (
              <button type="button" key={span.id} onClick={() => onSelectSpan(span)} className="flex w-full items-center gap-3 rounded-xl border border-stone-200 bg-white p-3 text-left transition hover:border-[#a00028] focus:outline-none focus:ring-2 focus:ring-[#e0301e]" aria-label={`View ${span.stage} trace details`}>
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#faf8f5] text-[#a00028]">
                  {span.status === "PASS" ? <CheckCircle2 className="h-4 w-4" /> : <CircleDashed className="h-4 w-4" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium text-stone-900">{span.stage}</p>
                    <StatusBadge tone={span.status}>{span.status}</StatusBadge>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-stone-500">
                    <span>{span.durationMs} ms</span>
                    <span>{span.identifier}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
          <p className="mt-4 text-sm text-stone-600">Total latency: {hardening.trace.totalLatencyMs} ms</p>
        </section>

        <section className="rounded-2xl border border-stone-300 bg-white p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">AX-606</p>
              <h3 className="mt-2 text-xl font-bold text-stone-900">Authorization hardening</h3>
            </div>
            <StatusBadge tone="GO">PASS</StatusBadge>
          </div>
          <div className="mt-5 space-y-3">
            {hardening.authorization.controls.map((control) => (
              <div key={control.label} className="flex items-center justify-between gap-3 rounded-xl border border-stone-200 bg-stone-50 p-3">
                <span className="font-medium text-stone-800">{control.label}</span>
                <StatusBadge tone={control.status}>{control.status}</StatusBadge>
              </div>
            ))}
          </div>
          <div className="mt-5 rounded-2xl border border-stone-200 bg-stone-50 p-4 text-sm text-stone-700">
            <div className="flex items-center justify-between"><span>Tests executed</span><strong>{hardening.authorization.testsExecuted}</strong></div>
            <div className="mt-2 flex items-center justify-between"><span>Passed</span><strong>{hardening.authorization.passed}</strong></div>
            <div className="mt-2 flex items-center justify-between"><span>Failed</span><strong>{hardening.authorization.failed}</strong></div>
            <div className="mt-2 flex items-center justify-between"><span>Last validation</span><strong>{formatDate(hardening.authorization.lastValidation)}</strong></div>
          </div>
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-2xl border border-stone-300 bg-white p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">AX-607</p>
              <h3 className="mt-2 text-xl font-bold text-stone-900">AI runtime monitoring</h3>
            </div>
            <StatusBadge tone="GO">PASS</StatusBadge>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <MetricCard label="Requests" value={hardening.monitoring.requests.toLocaleString()} detail="Total requests" icon={Clock3} accent="text-[#a00028]" />
            <MetricCard label="Success rate" value={`${hardening.monitoring.successRate}%`} detail="Stable behavior" icon={CheckCircle2} accent="text-emerald-700" />
            <MetricCard label="Average latency" value={`${(hardening.monitoring.averageLatencyMs / 1000).toFixed(1)}s`} detail="P95 health" icon={Gauge} accent="text-violet-700" />
            <MetricCard label="Tokens" value={hardening.monitoring.tokens.toLocaleString()} detail="Total consumed" icon={BrainCircuit} accent="text-[#a00028]" />
          </div>
          <div className="mt-5 overflow-hidden rounded-xl border border-stone-200">
            <table className="w-full text-left text-sm">
              <thead className="bg-stone-50 text-stone-600">
                <tr>
                  <th className="p-3">Model</th>
                  <th className="p-3">Requests</th>
                  <th className="p-3">Avg latency</th>
                  <th className="p-3">Success</th>
                  <th className="p-3">Retries</th>
                </tr>
              </thead>
              <tbody>
                {hardening.monitoring.modelMetrics.map((item) => (
                  <tr key={item.model} className="border-t border-stone-200">
                    <td className="p-3 font-medium text-stone-900">{item.model}</td>
                    <td className="p-3 text-stone-700">{item.requests}</td>
                    <td className="p-3 text-stone-700">{(item.avgLatencyMs / 1000).toFixed(1)}s</td>
                    <td className="p-3 text-stone-700">{item.successRate}%</td>
                    <td className="p-3 text-stone-700">{item.retries}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rounded-2xl border border-stone-300 bg-white p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">AX-608</p>
              <h3 className="mt-2 text-xl font-bold text-stone-900">AI quality & safety</h3>
            </div>
            <StatusBadge tone="GO">PASS</StatusBadge>
          </div>
          <div className="mt-5 space-y-4">
            {hardening.quality.metrics.map((metric) => (
              <div key={metric.label}>
                <div className="mb-1 flex items-center justify-between gap-2 text-sm text-stone-700">
                  <span>{metric.label}</span>
                  <span>{metric.value}%</span>
                </div>
                <div className="h-2.5 rounded-full bg-stone-200">
                  <div className="h-2.5 rounded-full bg-[#a00028]" style={{ width: `${Math.min(100, metric.value)}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-5 rounded-2xl border border-stone-200 bg-stone-50 p-4 text-sm text-stone-700">
            <p className="font-semibold text-stone-900">AI Evaluation</p>
            <p className="mt-2 text-2xl font-bold text-stone-900">PASS</p>
            <p className="mt-1">{hardening.quality.thresholdMet}</p>
          </div>
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-2xl border border-stone-300 bg-white p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">AX-609</p>
              <h3 className="mt-2 text-xl font-bold text-stone-900">Security review</h3>
            </div>
            <StatusBadge tone="GO">APPROVED</StatusBadge>
          </div>
          <div className="mt-5 space-y-3">
            {hardening.security.controls.map((control) => (
              <div key={control.name} className="flex items-center justify-between gap-3 rounded-xl border border-stone-200 bg-stone-50 p-3">
                <div>
                  <p className="font-medium text-stone-900">{control.name}</p>
                  <p className="text-xs text-stone-500">{control.summary}</p>
                </div>
                <StatusBadge tone={control.status}>{control.status}</StatusBadge>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-stone-300 bg-white p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">AX-610</p>
              <h3 className="mt-2 text-xl font-bold text-stone-900">Demonstration journey</h3>
            </div>
            <StatusBadge tone="GO">PASSED</StatusBadge>
          </div>
          <div className="mt-5 rounded-2xl border border-stone-200 bg-stone-50 p-4">
            <p className="text-sm text-stone-600">7 / 7 steps completed</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {hardening.regression.steps.map((step) => (
                <div key={step.label} className={`rounded-full px-3 py-1 text-xs font-semibold ${step.status === "done" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-stone-100 text-stone-500 border border-stone-200"}`}>
                  {step.status === "done" ? "✓" : "•"} {step.label}
                </div>
              ))}
            </div>
            <div className="mt-4 text-sm text-stone-700">
              <p>Execution: {formatDetailedDate(hardening.regression.execution)}</p>
              <p className="mt-1">Duration: {hardening.regression.duration}</p>
              <p className="mt-1">Environment: {hardening.regression.environment}</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

export default function ReleaseReadinessPage() {
  const [releases, setReleases] = useState<ReleaseRecord[]>(mockReleaseReadinessData);
  const [selectedReleaseId, setSelectedReleaseId] = useState(mockReleaseReadinessData[0].id);
  const [selectedTab, setSelectedTab] = useState<"readiness" | "hardening">("readiness");
  const [selectedCriterion, setSelectedCriterion] = useState<ReadinessCriterion | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(null);
  const [selectedTraceSpan, setSelectedTraceSpan] = useState<TraceSpan | null>(null);
  const [showDecisionModal, setShowDecisionModal] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const selectedRelease = useMemo(() => releases.find((release) => release.id === selectedReleaseId) ?? releases[0], [releases, selectedReleaseId]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    window.setTimeout(() => setIsRefreshing(false), 650);
  };

  const handleDecisionConfirm = (decision: string, rationale: string, conditionsText: string) => {
    const resolvedDecision: ReleaseDecisionHistoryEntry["decision"] =
      decision === "GO" || decision === "CONDITIONAL GO" || decision === "NO-GO" || decision === "Decision deferred"
        ? decision
        : "Decision deferred";

    const newEntry: ReleaseDecisionHistoryEntry = {
      id: `decision-${Date.now()}`,
      decision: resolvedDecision,
      owner: selectedRelease.decisionOwner,
      role: "Release Director",
      timestamp: new Date().toISOString(),
      rationale: rationale || "Recorded by authorized decision owner.",
      conditions: conditionsText ? conditionsText.split("\n").map((sentence) => sentence.trim()).filter(Boolean) : [],
    };

    const nextStatus: ReleaseRecord["status"] = resolvedDecision === "Decision deferred" ? "PENDING" : resolvedDecision;

    setReleases((previous) => previous.map((release) => release.id === selectedReleaseId ? { ...release, currentDecision: newEntry, decisionHistory: [newEntry, ...release.decisionHistory], status: nextStatus } : release));
    setShowDecisionModal(false);
  };

  return (
    <main className="min-h-full bg-[#faf8f5] p-5 text-[#1b1b1b] md:p-8">
      <header className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#a00028]">Release governance</p>
          <h1 className="mt-2 font-display text-3xl font-bold text-stone-900 md:text-4xl">Release Readiness</h1>
          <p className="mt-2 max-w-2xl text-stone-600">Assess evidence, blockers, and governance controls before production deployment.</p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="flex items-center gap-2 rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-stone-700">
            <Rocket className="h-4 w-4 text-[#a00028]" />
            <select value={selectedReleaseId} onChange={(event) => setSelectedReleaseId(event.target.value)} className="bg-transparent font-medium text-stone-800 outline-none">
              {releases.map((release) => (
                <option key={release.id} value={release.id}>{release.name}</option>
              ))}
            </select>
          </label>
          <div className="rounded-xl border border-stone-300 bg-white p-3 text-sm text-stone-700">
            <span className="font-medium text-stone-900">{selectedRelease.environment}</span>
            <span className="ml-2 text-stone-500">{formatDate(selectedRelease.targetDate)}</span>
          </div>
          <button type="button" onClick={handleRefresh} className="inline-flex items-center justify-center gap-2 rounded-xl border border-stone-300 bg-white px-4 py-2.5 text-sm font-semibold text-stone-700">
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} /> Refresh evaluation
          </button>
          <button type="button" onClick={() => setShowDecisionModal(true)} className="rounded-xl bg-[#a00028] px-4 py-2.5 text-sm font-semibold text-white">Record Decision</button>
        </div>
      </header>

      <div className="mt-6 rounded-2xl border border-stone-300 bg-white p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">Selected release</p>
            <h2 className="mt-2 text-2xl font-bold text-stone-900">{selectedRelease.name}</h2>
          </div>
          <div className="flex flex-wrap gap-2 text-sm text-stone-600">
            <span className="rounded-full bg-stone-100 px-2.5 py-1">Environment: {selectedRelease.environment}</span>
            <span className="rounded-full bg-stone-100 px-2.5 py-1">Target: {formatDetailedDate(selectedRelease.targetDate)}</span>
            <span className="rounded-full bg-stone-100 px-2.5 py-1">Owner: {selectedRelease.releaseOwner}</span>
          </div>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-2 border-b border-stone-300 pb-3">
        {[{ id: "readiness", label: "Release Readiness" }, { id: "hardening", label: "Hardening" }].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setSelectedTab(tab.id as "readiness" | "hardening")}
            className={`rounded-xl px-3 py-2 text-sm font-semibold ${selectedTab === tab.id ? "bg-[#a00028] text-white" : "bg-white text-stone-700 border border-stone-300"}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {selectedTab === "readiness" ? (
        <div className="mt-6">
          <ReleaseReadinessTab selectedRelease={selectedRelease} onSelectCriterion={setSelectedCriterion} onOpenEvidence={setSelectedEvidence} />
        </div>
      ) : (
        <div className="mt-6">
          <HardeningTab selectedRelease={selectedRelease} onSelectSpan={setSelectedTraceSpan} />
        </div>
      )}

      <CriterionDrawer criterion={selectedCriterion} onClose={() => setSelectedCriterion(null)} onOpenEvidence={setSelectedEvidence} />
      <EvidenceModal evidence={selectedEvidence} onClose={() => setSelectedEvidence(null)} />
      <TraceSpanDrawer span={selectedTraceSpan} traceId={selectedRelease.hardening.trace.id} onClose={() => setSelectedTraceSpan(null)} />
      <RecordDecisionModal open={showDecisionModal} onClose={() => setShowDecisionModal(false)} currentDecision={selectedRelease.currentDecision} onConfirm={handleDecisionConfirm} selectedRelease={selectedRelease} />
    </main>
  );
}
