import { useState } from "react";
import { CheckCircle2, ChevronRight, Clock3, FileCheck2, Gauge, GitBranch, RefreshCw, ShieldCheck, ShieldAlert, TriangleAlert, X, Zap } from "lucide-react";
import { Link, NavLink, useParams } from "react-router-dom";
import { isDeliveryMockMode } from "../../config/deliveryDataMode";
import { useRelease } from "../../hooks/useReleases";
import ReleaseNotesPage from "./ReleaseNotesPage";
import { calculateReleaseReadiness, calculateReleaseRecommendation } from "./utils/calculateReleaseReadiness";
import type { EvidenceItem, ReadinessCriterion, Release, ReleaseDecision, TraceSpan } from "./types";

const formatDate = (value: string) => new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
const formatShortDate = (value: string) => new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value));

function StatusPill({ children, tone = "neutral" }: { children: string; tone?: "neutral" | "success" | "warning" | "danger" | "purple" }) {
  const palette = {
    neutral: "bg-stone-100 text-stone-700 border border-stone-200",
    success: "bg-emerald-50 text-emerald-700 border border-emerald-200",
    warning: "bg-amber-50 text-amber-800 border border-amber-200",
    danger: "bg-red-50 text-red-700 border border-red-200",
    purple: "bg-violet-50 text-violet-700 border border-violet-200",
  }[tone];

  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ${palette}`}>{children}</span>;
}

function Card({ title, value, detail, icon: Icon }: { title: string; value: string; detail: string; icon: typeof Gauge }) {
  return (
    <div className="rounded-2xl border border-stone-300 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">{title}</p>
          <p className="mt-3 text-3xl font-bold text-stone-900">{value}</p>
        </div>
        <div className="rounded-xl bg-[#faf8f5] p-2 text-[#a00028]"><Icon className="h-5 w-5" /></div>
      </div>
      <p className="mt-3 text-sm text-stone-600">{detail}</p>
    </div>
  );
}

function SideDrawer({ title, eyebrow, onClose, children }: { title: string; eyebrow: string; onClose: () => void; children: React.ReactNode }) {
  return <div className="fixed inset-0 z-40 bg-stone-950/35" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <aside className="absolute inset-y-0 right-0 w-full max-w-lg overflow-y-auto border-l border-stone-300 bg-[#faf8f5] p-6 shadow-2xl" role="dialog" aria-modal="true" aria-labelledby="release-drawer-title">
      <div className="flex items-start justify-between gap-3"><div><p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#a00028]">{eyebrow}</p><h2 id="release-drawer-title" className="mt-2 text-2xl font-bold text-stone-900">{title}</h2></div><button type="button" onClick={onClose} aria-label="Close details" className="rounded-full p-2 text-stone-500 hover:bg-stone-200 focus:outline-none focus:ring-2 focus:ring-[#e0301e]"><X className="h-4 w-4" /></button></div>
      {children}
    </aside>
  </div>;
}

function RecordDecisionModal({ release, onClose, onRecord }: { release: Release; onClose: () => void; onRecord: (decision: ReleaseDecision) => void }) {
  const [decision, setDecision] = useState<ReleaseDecision["decision"]>("CONDITIONAL GO");
  const [rationale, setRationale] = useState("");
  const [conditions, setConditions] = useState(release.conditions.map((item) => item.summary).join("\n"));
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const submit = () => {
    if (decision === "CONDITIONAL GO" && !conditions.trim()) return setError("Add at least one release condition.");
    if (decision === "NO-GO" && !rationale.trim()) return setError("A rationale is required for a No-Go decision.");
    setError("");
    setConfirming(true);
  };
  const confirm = () => onRecord({ decision, owner: release.decisionOwner, role: "Release Director", timestamp: new Date().toISOString(), rationale: rationale.trim() || "Recorded by the authorized release decision owner.", conditions: conditions.split("\n").map((item) => item.trim()).filter(Boolean) });
  return <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-stone-950/45 p-4 sm:items-center" role="dialog" aria-modal="true" aria-labelledby="decision-title">
    <div className="my-auto w-full max-w-xl rounded-2xl border border-stone-300 bg-white p-6 shadow-2xl">
      <div className="flex items-start justify-between gap-3"><div><p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#a00028]">Human governance</p><h2 id="decision-title" className="mt-2 text-2xl font-bold text-stone-900">Record release decision</h2></div><button type="button" onClick={onClose} aria-label="Close decision dialog" className="rounded-full p-2 text-stone-500 hover:bg-stone-100"><X className="h-4 w-4" /></button></div>
      {confirming ? <>
        <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-950"><p className="text-sm font-semibold">Confirm release decision</p><p className="mt-3 text-2xl font-bold">{decision}</p><p className="mt-2 text-sm">for {release.name} — {release.environment}</p><p className="mt-4 text-sm">This governance decision will be recorded in the release audit history.</p><p className="mt-4 text-sm"><strong>Decision owner:</strong> {release.decisionOwner}</p></div>
        <div className="mt-5 flex justify-end gap-3"><button type="button" onClick={() => setConfirming(false)} className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-semibold">Back</button><button type="button" onClick={confirm} className="rounded-xl bg-[#a00028] px-4 py-2 text-sm font-semibold text-white">Confirm decision</button></div>
      </> : <>
      <div className="mt-5 rounded-xl border border-violet-200 bg-violet-50 p-3 text-sm text-violet-800"><strong>AI recommendation:</strong> {release.recommendation}</div>
      <fieldset className="mt-5 space-y-2"><legend className="text-sm font-semibold text-stone-900">Final human decision</legend>{(["GO", "CONDITIONAL GO", "NO-GO"] as const).map((option) => <label key={option} className="flex items-center gap-3 rounded-xl border border-stone-300 p-3 text-sm"><input type="radio" name="release-decision" checked={decision === option} onChange={() => { setDecision(option); setError(""); }} />{option}</label>)}</fieldset>
      <label className="mt-4 block text-sm font-medium text-stone-700">Decision rationale<textarea rows={3} value={rationale} onChange={(event) => setRationale(event.target.value)} className="mt-2 w-full rounded-xl border border-stone-300 bg-stone-50 p-3" /></label>
      <label className="mt-4 block text-sm font-medium text-stone-700">Conditions<textarea rows={3} value={conditions} onChange={(event) => setConditions(event.target.value)} className="mt-2 w-full rounded-xl border border-stone-300 bg-stone-50 p-3" /></label>
      <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">You are recording the final release governance decision. This action will be recorded in the audit history.</p>
      {error && <p className="mt-3 text-sm font-medium text-rose-700" role="alert">{error}</p>}
      <div className="mt-5 flex justify-end gap-3"><button type="button" onClick={onClose} className="rounded-xl border border-stone-300 px-4 py-2 text-sm font-semibold">Cancel</button><button type="button" onClick={submit} className="rounded-xl bg-[#a00028] px-4 py-2 text-sm font-semibold text-white">Continue</button></div>
      </>}
    </div>
  </div>;
}

function ReleaseOverview({ release }: { release: Release }) {
  const readiness = calculateReleaseReadiness(release.criteria);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card title="Readiness score" value={`${release.readinessScore}%`} detail={`${readiness.passed} / ${readiness.total} criteria passed`} icon={Gauge} />
        <Card title="AI recommendation" value={release.recommendation} detail="Generated from release evidence" icon={Zap} />
        <Card title="Open blockers" value={String(release.blockers.length)} detail={release.blockers.length ? `${release.blockers[0].severity} blocker` : "No blockers"} icon={ShieldAlert} />
        <Card title="Evidence coverage" value={`${Math.round((release.evidenceSummary.verified / Math.max(release.evidenceSummary.total, 1)) * 100)}%`} detail={`${release.evidenceSummary.verified} / ${release.evidenceSummary.total} verified`} icon={FileCheck2} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
          <h2 className="text-xl font-bold text-stone-900">Release Timeline</h2>
          <div className="mt-5 space-y-4">
            {[
              { label: "Planning", complete: true },
              { label: "Code Complete", complete: true },
              { label: "SIT", complete: true },
              { label: "UAT", complete: true },
              { label: "Regression", complete: true },
              { label: "Go / No-Go", complete: release.currentDecision !== null },
              { label: "Deployment", complete: release.lifecycle === "DEPLOYED" || release.lifecycle === "DEPLOYING" },
              { label: "Hypercare", complete: false },
            ].map((step) => (
              <div key={step.label} className="flex items-center gap-3">
                <div className={`flex h-7 w-7 items-center justify-center rounded-full ${step.complete ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                  {step.complete ? <CheckCircle2 className="h-4 w-4" /> : <Clock3 className="h-4 w-4" />}
                </div>
                <span className="font-medium text-stone-800">{step.label}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
          <h2 className="text-xl font-bold text-stone-900">Summary information</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-3 border-b border-stone-200 pb-2"><dt className="text-stone-500">Release ID</dt><dd className="font-semibold text-stone-900">{release.releaseId}</dd></div>
            <div className="flex justify-between gap-3 border-b border-stone-200 pb-2"><dt className="text-stone-500">Version</dt><dd className="font-semibold text-stone-900">{release.version}</dd></div>
            <div className="flex justify-between gap-3 border-b border-stone-200 pb-2"><dt className="text-stone-500">Release type</dt><dd className="font-semibold text-stone-900">{release.releaseType}</dd></div>
            <div className="flex justify-between gap-3 border-b border-stone-200 pb-2"><dt className="text-stone-500">Environment</dt><dd className="font-semibold text-stone-900">{release.environment}</dd></div>
            <div className="flex justify-between gap-3 border-b border-stone-200 pb-2"><dt className="text-stone-500">Target deployment</dt><dd className="font-semibold text-stone-900">{formatDate(release.targetDate)}</dd></div>
            <div className="flex justify-between gap-3 border-b border-stone-200 pb-2"><dt className="text-stone-500">Release owner</dt><dd className="font-semibold text-stone-900">{release.releaseOwner}</dd></div>
            <div className="flex justify-between gap-3 border-b border-stone-200 pb-2"><dt className="text-stone-500">Business owner</dt><dd className="font-semibold text-stone-900">{release.businessOwner}</dd></div>
            <div className="flex justify-between gap-3 border-b border-stone-200 pb-2"><dt className="text-stone-500">Technical owner</dt><dd className="font-semibold text-stone-900">{release.technicalOwner}</dd></div>
            <div className="flex justify-between gap-3 border-b border-stone-200 pb-2"><dt className="text-stone-500">Current phase</dt><dd className="font-semibold text-stone-900">{release.phase}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-stone-500">Change / CAB</dt><dd className="font-semibold text-stone-900">{release.changeReference}</dd></div>
          </dl>
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
          <h2 className="text-xl font-bold text-stone-900">Top blockers</h2>
          <div className="mt-4 space-y-3">
            {release.blockers.length ? release.blockers.map((blocker) => (
              <div key={blocker.id} className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-stone-500">{blocker.id}</p>
                    <h3 className="mt-2 text-base font-semibold text-stone-900">{blocker.title}</h3>
                  </div>
                  <StatusPill tone={blocker.severity === "Critical" ? "danger" : blocker.severity === "High" ? "warning" : "neutral"}>{blocker.severity}</StatusPill>
                </div>
                <p className="mt-3 text-sm text-stone-600">Owner: {blocker.owner}</p>
                <p className="text-sm text-stone-600">Due: {blocker.due}</p>
              </div>
            )) : <p className="text-sm text-stone-600">No open blockers.</p>}
          </div>
        </section>

        <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
          <h2 className="text-xl font-bold text-stone-900">Recent activity</h2>
          <div className="mt-4 space-y-3">
            {release.decisionHistory.map((entry) => (
              <div key={entry.id} className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-stone-900">{entry.decision}</p>
                  <span className="text-xs text-stone-500">{formatShortDate(entry.timestamp)}</span>
                </div>
                <p className="mt-2 text-sm text-stone-600">{entry.owner} · {entry.role}</p>
                <p className="mt-2 text-sm text-stone-700">{entry.rationale}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function ReleaseReadiness({ release, canApproveRelease, onRecordDecision }: { release: Release; canApproveRelease: boolean; onRecordDecision: () => void }) {
  const readiness = calculateReleaseReadiness(release.criteria);
  const evidenceCoverage = Math.round((release.evidenceSummary.verified / Math.max(release.evidenceSummary.total, 1)) * 100);
  const verifiedEvidence = release.evidenceSummary.verified;
  const totalEvidence = release.evidenceSummary.total;
  const recommendation = calculateReleaseRecommendation(release.criteria, evidenceCoverage);
  const [selectedCriterion, setSelectedCriterion] = useState<ReadinessCriterion | null>(null);

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">Release readiness</p>
            <h2 className="mt-2 text-2xl font-bold text-stone-900">{release.name}</h2>
            <p className="mt-2 text-sm text-stone-600">Evaluate delivery evidence and governance controls before production deployment.</p>
          </div>
          <div className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-700">
            <div className="font-semibold text-stone-900">{release.environment}</div>
            <div>{formatDate(release.targetDate)}</div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card title="Readiness score" value={`${readiness.percentage}%`} detail={`${readiness.passed} / ${readiness.total} criteria passed`} icon={Gauge} />
        <Card title="AI recommendation" value={recommendation} detail={`${release.conditions.length} conditions outstanding`} icon={Zap} />
        <Card title="Blocking items" value={String(release.blockers.length)} detail={release.blockers[0]?.title ?? "No blocking criteria"} icon={ShieldAlert} />
        <Card title="Evidence coverage" value={`${evidenceCoverage}%`} detail={`${verifiedEvidence} / ${totalEvidence} evidence items verified`} icon={FileCheck2} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-4"><div><p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">Readiness breakdown</p><p className="mt-2 text-3xl font-bold text-stone-900">{readiness.percentage}%</p></div><StatusPill tone={readiness.blocked ? "warning" : "success"}>{release.lifecycle}</StatusPill></div>
          <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-stone-200"><div className="h-full rounded-full bg-[#a00028]" style={{ width: `${readiness.percentage}%` }} /></div>
          <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2"><div className="rounded-xl bg-stone-50 p-3"><dt className="text-stone-500">Passed criteria</dt><dd className="mt-1 font-bold text-stone-900">{readiness.passed}</dd></div><div className="rounded-xl bg-stone-50 p-3"><dt className="text-stone-500">Missing evidence</dt><dd className="mt-1 font-bold text-stone-900">{totalEvidence - verifiedEvidence}</dd></div><div className="rounded-xl bg-stone-50 p-3"><dt className="text-stone-500">Blocking criteria</dt><dd className="mt-1 font-bold text-stone-900">{readiness.blocked}</dd></div><div className="rounded-xl bg-stone-50 p-3"><dt className="text-stone-500">Conditions / exceptions</dt><dd className="mt-1 font-bold text-stone-900">{release.conditions.length} / {release.exceptions.length}</dd></div></dl>
        </section>
        <section className="rounded-2xl border border-violet-200 bg-violet-50 p-5 shadow-sm">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-violet-700">AI release recommendation</p><h2 className="mt-3 text-2xl font-bold text-violet-950">{recommendation}</h2><p className="mt-3 text-sm leading-6 text-violet-900">The release is substantially ready for production. Deployment can proceed provided the outstanding mandatory conditions are satisfied before the production window.</p>
          <h3 className="mt-5 text-sm font-semibold text-violet-950">Why this recommendation?</h3><ul className="mt-2 space-y-1 text-sm text-violet-900"><li>✓ Code, SIT, UAT and regression complete</li><li>✓ CAB, business approval and rollback controls validated</li><li>! Security approval pending</li><li>! Monitoring validation remains conditional</li></ul>
          <div className="mt-5 border-t border-violet-200 pt-4 text-sm text-violet-900"><p><strong>Evidence confidence:</strong> HIGH</p><p className="mt-1"><strong>Coverage:</strong> {evidenceCoverage}%</p><p className="mt-1"><strong>Last evaluated:</strong> 04 Oct 2026 · 09:42</p></div>
          <p className="mt-4 text-xs leading-5 text-violet-800">AX provides a recommendation based on available release evidence. Final release authority remains with the authorized human decision owner.</p>
        </section>
      </div>

      <div className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
        <h2 className="text-xl font-bold text-stone-900">Readiness criteria</h2>
        <div className="mt-5 grid gap-3 xl:grid-cols-2">
          {release.criteria.map((criterion) => (
            <button type="button" key={criterion.id} onClick={() => setSelectedCriterion(criterion)} className="rounded-2xl border border-stone-200 bg-stone-50 p-4 text-left transition hover:border-[#a00028] focus:outline-none focus:ring-2 focus:ring-[#e0301e]">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-stone-900">{criterion.name}</p>
                  <p className="mt-1 text-sm text-stone-600">{criterion.note}</p>
                </div>
                <StatusPill tone={criterion.status === "PASSED" ? "success" : criterion.status === "CONDITIONAL" ? "purple" : criterion.status === "PENDING" || criterion.status === "MISSING EVIDENCE" ? "warning" : "danger"}>{criterion.status}</StatusPill>
              </div>
              <div className="mt-4 grid gap-2 text-xs text-stone-600 sm:grid-cols-2">
                <div>
                  <span className="block text-stone-500">Owner</span>
                  <strong className="mt-1 block text-stone-800">{criterion.owner}</strong>
                </div>
                <div>
                  <span className="block text-stone-500">Updated</span>
                  <strong className="mt-1 block text-stone-800">{formatShortDate(criterion.lastUpdated)}</strong>
                </div>
              </div>
              <div className="mt-4 flex items-center justify-between gap-3 text-xs text-stone-600">
                <span className={`rounded-full px-2 py-1 font-medium ${criterion.mandatory ? "bg-red-50 text-red-700" : "bg-stone-200 text-stone-700"}`}>{criterion.mandatory ? "Mandatory" : "Optional"}</span>
                {criterion.blocking ? <span className="font-medium text-red-600">Blocking</span> : <span>Non-blocking</span>}
              </div>
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm"><div className="flex items-center justify-between"><h2 className="text-xl font-bold text-stone-900">Open blockers</h2><StatusPill tone={release.blockers.length ? "danger" : "success"}>{`${release.blockers.length} OPEN`}</StatusPill></div>{release.blockers.length ? <div className="mt-4 space-y-3">{release.blockers.map((blocker) => <article key={blocker.id} className="rounded-xl border border-rose-200 bg-rose-50 p-4"><div className="flex justify-between gap-3"><div><p className="text-xs font-bold text-rose-700">{blocker.id}</p><h3 className="mt-1 font-semibold text-rose-950">{blocker.title}</h3></div><StatusPill tone="danger">{blocker.severity.toUpperCase()}</StatusPill></div><p className="mt-3 text-sm text-rose-900">Owner: {blocker.owner} · Due: {blocker.due}</p><p className="mt-2 text-sm text-rose-900">Production deployment cannot proceed without formal approval.</p></article>)}</div> : <p className="mt-4 text-sm text-stone-600">No blocking release criteria are currently outstanding.</p>}</section>
        <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold text-stone-900">Conditions & approved exceptions</h2><div className="mt-4 space-y-3">{release.conditions.map((condition) => <div key={condition.id} className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950"><strong>Condition:</strong> {condition.summary}<p className="mt-1 text-xs">{condition.owner} · {formatShortDate(condition.due)} · OPEN</p></div>)}{release.exceptions.map((exception) => <div key={exception.id} className="rounded-xl border border-violet-200 bg-violet-50 p-3 text-sm text-violet-950"><strong>Approved exception:</strong> {exception.summary}<p className="mt-1 text-xs">Approved by {exception.approvedBy} · Valid until {formatShortDate(exception.validUntil ?? exception.due)}</p></div>)}</div></section>
      </div>

      <section className="rounded-2xl border-2 border-stone-400 bg-white p-5 shadow-sm"><div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between"><div><p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">Go / No-Go decision</p><div className="mt-4 grid gap-4 sm:grid-cols-2"><div><p className="text-sm text-stone-500">AI recommendation</p><p className="mt-1 text-xl font-bold text-violet-800">{recommendation}</p></div><div><p className="text-sm text-stone-500">Human decision</p><p className="mt-1 text-xl font-bold text-stone-900">{release.currentDecision?.decision ?? "PENDING"}</p></div></div><p className="mt-4 text-sm text-stone-700"><strong>Decision owner:</strong> {release.decisionOwner} · Release Director</p><p className="mt-1 text-sm text-stone-700"><strong>Decision authority:</strong> Authorized</p><p className="mt-1 text-sm text-stone-600">{release.blockers.length} blocker · {release.conditions.length} conditions · {release.exceptions.length} approved exception</p></div>{canApproveRelease ? <button type="button" onClick={onRecordDecision} className="rounded-xl bg-[#a00028] px-4 py-2.5 text-sm font-semibold text-white">Record Decision</button> : <p className="max-w-xs text-sm text-stone-600">You do not have permission to record this release decision.</p>}</div></section>

      <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold text-stone-900">Decision history</h2><div className="mt-4 space-y-3">{release.decisionHistory.length ? release.decisionHistory.map((entry) => <article key={entry.id} className="border-l-2 border-stone-300 py-2 pl-4"><div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-stone-900">{entry.decision}</strong><time className="text-xs text-stone-500">{formatDate(entry.timestamp)}</time></div><p className="mt-1 text-sm text-stone-600">{entry.owner} · {entry.role}</p><p className="mt-2 text-sm text-stone-700">{entry.rationale}</p>{entry.conditions?.length ? <p className="mt-2 text-xs text-stone-500">Conditions: {entry.conditions.length} · AI recommendation at decision time: {release.recommendation}</p> : null}</article>) : <p className="text-sm text-stone-600">No release decision has been recorded.</p>}</div></section>

      <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold text-stone-900">Recent readiness activity</h2><div className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-5">{[["09:42", "Readiness recalculated · 79% → 87%"], ["09:21", "Security review requested"], ["08:55", "Regression evidence verified"], ["08:41", "Monitoring evidence added"], ["07:52", "CAB approval recorded"]].map(([time, activity]) => <div key={time} className="rounded-xl bg-stone-50 p-3"><time className="font-semibold text-stone-900">{time}</time><p className="mt-1 text-stone-600">{activity}</p></div>)}</div></section>
      {selectedCriterion && <SideDrawer title={selectedCriterion.name} eyebrow="Readiness criterion" onClose={() => setSelectedCriterion(null)}>
        <div className="mt-5 flex gap-2"><StatusPill tone={selectedCriterion.status === "PASSED" ? "success" : "warning"}>{selectedCriterion.status}</StatusPill>{selectedCriterion.blocking && <StatusPill tone="danger">BLOCKING</StatusPill>}</div>
        <dl className="mt-5 divide-y divide-stone-200 rounded-2xl border border-stone-300 bg-white px-4 text-sm"><div className="flex justify-between gap-4 py-3"><dt className="text-stone-500">Owner</dt><dd className="font-semibold text-stone-900">{selectedCriterion.owner}</dd></div><div className="py-3"><dt className="text-stone-500">Requirement</dt><dd className="mt-1 text-stone-900">{selectedCriterion.note}</dd></div><div className="py-3"><dt className="text-stone-500">Evidence</dt><dd className="mt-1 text-stone-900">{selectedCriterion.evidenceLabel ?? "Approval evidence missing"}</dd></div><div className="flex justify-between gap-4 py-3"><dt className="text-stone-500">Updated</dt><dd className="font-semibold text-stone-900">{formatDate(selectedCriterion.lastUpdated)}</dd></div></dl>
        <section className="mt-5"><h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-stone-500">Related evidence</h3><ul className="mt-3 space-y-2 text-sm text-stone-700"><li>Penetration Test Report</li><li>Vulnerability Scan</li><li>Security Review AX-184</li></ul></section>
        <section className="mt-5"><h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-stone-500">History</h3><p className="mt-2 text-sm text-stone-700">03 Oct 16:10 — Review requested</p><p className="mt-1 text-sm text-stone-700">02 Oct 11:42 — Evidence submitted</p></section>
        <div className="mt-6 flex flex-wrap gap-2"><button type="button" className="rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm font-semibold">View Evidence</button><button type="button" className="rounded-xl bg-[#a00028] px-3 py-2 text-sm font-semibold text-white">Add Evidence</button><button type="button" className="rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm font-semibold">Request Review</button></div>
      </SideDrawer>}
    </div>
  );
}

function ReleaseEvidence({ release }: { release: Release }) {
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(null);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <Card title="Total evidence" value={String(release.evidenceSummary.total)} detail="Records in the release package" icon={FileCheck2} />
        <Card title="Verified" value={String(release.evidenceSummary.verified)} detail="Evidence has been validated" icon={CheckCircle2} />
        <Card title="Missing" value={String(release.evidenceSummary.missing)} detail={`${release.evidenceSummary.expired} expired evidence records`} icon={TriangleAlert} />
      </div>

      <div className="overflow-hidden rounded-2xl border border-stone-300 bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-stone-50 text-[11px] font-bold uppercase tracking-[0.16em] text-stone-500">
            <tr>
              <th className="px-4 py-3">Evidence</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">Linked criterion</th>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3">Owner</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Recorded</th>
            </tr>
          </thead>
          <tbody>
            {release.evidence.length ? release.evidence.map((item) => (
              <tr key={item.id} className="cursor-pointer border-t border-stone-200 hover:bg-stone-50" onClick={() => setSelectedEvidence(item)}>
                <td className="px-4 py-3 font-medium text-stone-900">{item.title}</td>
                <td className="px-4 py-3 text-stone-700">{item.category}</td>
                <td className="px-4 py-3 text-stone-700">{item.linkedCriterion}</td>
                <td className="px-4 py-3 text-stone-700">{item.source}</td>
                <td className="px-4 py-3 text-stone-700">{item.owner}</td>
                <td className="px-4 py-3"><StatusPill tone={item.status === "VERIFIED" ? "success" : item.status === "PENDING" ? "warning" : "danger"}>{item.status}</StatusPill></td>
                <td className="px-4 py-3 text-stone-500">{formatShortDate(item.recorded)}</td>
              </tr>
            )) : <tr><td colSpan={7} className="px-4 py-6 text-center text-stone-600">No release evidence has been recorded yet.</td></tr>}
          </tbody>
        </table>
      </div>
      {selectedEvidence && <SideDrawer title={selectedEvidence.title} eyebrow="Release evidence" onClose={() => setSelectedEvidence(null)}><dl className="mt-5 divide-y divide-stone-200 rounded-2xl border border-stone-300 bg-white px-4 text-sm">{[["Status", selectedEvidence.status], ["Type", selectedEvidence.category], ["Source", selectedEvidence.source], ["Owner", selectedEvidence.owner], ["Recorded", formatDate(selectedEvidence.recorded)], ["Linked criterion", selectedEvidence.linkedCriterion]].map(([label, value]) => <div key={label} className="flex justify-between gap-4 py-3"><dt className="text-stone-500">{label}</dt><dd className="text-right font-semibold text-stone-900">{value}</dd></div>)}</dl><div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"><p>Source verified</p><p>Timestamp validated</p><p>Owner matched</p></div><button type="button" className="mt-5 rounded-xl bg-[#a00028] px-4 py-2 text-sm font-semibold text-white">Open source</button></SideDrawer>}
    </div>
  );
}

function ReleaseRisks({ release }: { release: Release }) {
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
        <h2 className="text-xl font-bold text-stone-900">Open blockers</h2>
        <div className="mt-4 space-y-3">
          {release.blockers.length ? release.blockers.map((blocker) => (
            <div key={blocker.id} className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="font-semibold text-stone-900">{blocker.title}</p>
                <StatusPill tone={blocker.severity === "Critical" ? "danger" : blocker.severity === "High" ? "warning" : "neutral"}>{blocker.severity}</StatusPill>
              </div>
              <div className="mt-2 text-sm text-stone-600">
                <p>Owner: {blocker.owner}</p>
                <p>Due: {blocker.due}</p>
                <p>Linked criterion: {blocker.linkedCriterion}</p>
              </div>
            </div>
          )) : <p className="text-sm text-stone-600">No open blockers.</p>}
        </div>
      </section>

      <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
        <h2 className="text-xl font-bold text-stone-900">Release risks</h2>
        <div className="mt-4 space-y-3">
          {release.risks.length ? release.risks.map((risk) => (
            <div key={risk.id} className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="font-semibold text-stone-900">{risk.title}</p>
                <StatusPill tone={risk.severity === "Critical" ? "danger" : risk.severity === "High" ? "warning" : "neutral"}>{risk.severity}</StatusPill>
              </div>
              <p className="mt-2 text-sm text-stone-600">Likelihood: {risk.likelihood} · Impact: {risk.impact}</p>
              <p className="mt-2 text-sm text-stone-700">Mitigation: {risk.mitigation}</p>
            </div>
          )) : <p className="text-sm text-stone-600">No release risks recorded.</p>}
        </div>
      </section>

      <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm xl:col-span-2">
        <h2 className="text-xl font-bold text-stone-900">Conditions & exceptions</h2>
        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-stone-500">Conditions</h3>
            <div className="mt-3 space-y-3">
              {release.conditions.length ? release.conditions.map((condition) => (
                <div key={condition.id} className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                  <p className="font-medium text-amber-900">{condition.summary}</p>
                  <p className="mt-2 text-sm text-amber-800">Owner: {condition.owner}</p>
                  <p className="text-sm text-amber-800">Due: {formatShortDate(condition.due)}</p>
                </div>
              )) : <p className="text-sm text-stone-600">No release conditions.</p>}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-stone-500">Approved exceptions</h3>
            <div className="mt-3 space-y-3">
              {release.exceptions.length ? release.exceptions.map((exception) => (
                <div key={exception.id} className="rounded-2xl border border-violet-200 bg-violet-50 p-4">
                  <p className="font-medium text-violet-800">{exception.summary}</p>
                  <p className="mt-2 text-sm text-violet-700">Approved by: {exception.approvedBy}</p>
                  <p className="text-sm text-violet-700">Valid until: {exception.validUntil ? formatShortDate(exception.validUntil) : "—"}</p>
                </div>
              )) : <p className="text-sm text-stone-600">No approved exceptions.</p>}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function ReleaseDecisions({ release }: { release: Release }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">Current decision</p>
          <h2 className="mt-3 text-3xl font-bold text-stone-900">{release.currentDecision?.decision ?? "PENDING"}</h2>
          <p className="mt-2 text-sm text-stone-600">Decision owner: {release.decisionOwner}</p>
        </div>
        <div className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">AI recommendation</p>
          <h2 className="mt-3 text-3xl font-bold text-stone-900">{release.recommendation}</h2>
          <p className="mt-2 text-sm text-stone-600">The recommendation is generated from available evidence. Final authority remains with the human decision owner.</p>
        </div>
      </div>

      <div className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
        <h2 className="text-xl font-bold text-stone-900">Decision history</h2>
        <div className="mt-5 space-y-4">
          {release.decisionHistory.map((entry) => (
            <div key={entry.id} className="rounded-2xl border border-stone-200 bg-stone-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-stone-900">{entry.decision}</p>
                <span className="text-xs text-stone-500">{formatShortDate(entry.timestamp)}</span>
              </div>
              <p className="mt-2 text-sm text-stone-600">{entry.owner} · {entry.role}</p>
              <p className="mt-2 text-sm text-stone-700">{entry.rationale}</p>
              {entry.conditions && entry.conditions.length > 0 && (
                <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-stone-600">
                  {entry.conditions.map((condition) => (
                    <li key={`${entry.id}-${condition}`}>{condition}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ReleaseHardening({ release }: { release: Release }) {
  const criticalFindings = release.hardening.security.controls.filter((control) => control.status === "FAIL").length;
  const [selectedSpan, setSelectedSpan] = useState<TraceSpan | null>(null);

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#a00028]">MVP hardening status</p>
            <h2 className="mt-2 text-2xl font-bold text-stone-900">READY</h2>
          </div>
          <StatusPill tone="success">PASS</StatusPill>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-6">
          <Card title="Tracing" value="PASS" detail={`${release.hardening.trace.spans.filter((span) => span.status === "PASS").length} / ${release.hardening.trace.spans.length} spans successful`} icon={GitBranch} />
          <Card title="Authorization" value={`${release.hardening.authorization.passed}/${release.hardening.authorization.testsExecuted}`} detail="Role and tenancy controls are validated" icon={ShieldCheck} />
          <Card title="AI monitoring" value="PASS" detail={`${release.hardening.monitoring.successRate}% success rate`} icon={CheckCircle2} />
          <Card title="AI evaluation" value={release.hardening.quality.overallStatus} detail={release.hardening.quality.thresholdMet} icon={Zap} />
          <Card title="Security" value={release.hardening.security.overallStatus} detail="0 critical · 0 high" icon={ShieldCheck} />
          <Card title="Regression" value={release.hardening.regression.status} detail={`${release.hardening.regression.steps.filter((step) => step.status === "done").length} / ${release.hardening.regression.steps.length} steps`} icon={CheckCircle2} />
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
          <h2 className="text-xl font-bold text-stone-900">End-to-end tracing</h2>
          <div className="mt-4 rounded-2xl border border-stone-200 bg-stone-50 p-4 text-sm text-stone-700">
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-stone-500">Trace ID</p>
            <p className="mt-2 font-mono text-sm text-stone-900">{release.hardening.trace.id}</p>
          </div>
          <div className="mt-5 space-y-3">
            {release.hardening.trace.spans.map((span) => (
              <button type="button" key={span.id} onClick={() => setSelectedSpan(span)} className="flex w-full items-center gap-3 rounded-2xl border border-stone-200 bg-white p-3 text-left hover:border-[#a00028] focus:outline-none focus:ring-2 focus:ring-[#e0301e]">
                <div className={`flex h-8 w-8 items-center justify-center rounded-full ${span.status === "PASS" ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                  {span.status === "PASS" ? <CheckCircle2 className="h-4 w-4" /> : <Clock3 className="h-4 w-4" />}
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium text-stone-900">{span.stage}</p>
                    <StatusPill tone={span.status === "PASS" ? "success" : span.status === "FAIL" ? "danger" : "warning"}>{span.status}</StatusPill>
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-3 text-xs text-stone-500">
                    <span>{span.durationMs} ms</span>
                    <span>{span.identifier}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
          <h2 className="text-xl font-bold text-stone-900">Security review</h2>
          <div className="mt-4 space-y-3">
            {release.hardening.security.controls.map((control) => (
              <div key={control.name} className="flex items-center justify-between gap-3 rounded-2xl border border-stone-200 bg-stone-50 p-3">
                <div>
                  <p className="font-medium text-stone-900">{control.name}</p>
                  <p className="text-xs text-stone-500">{control.summary}</p>
                </div>
                <StatusPill tone={control.status === "PASS" ? "success" : control.status === "FAIL" ? "danger" : "warning"}>{control.status}</StatusPill>
              </div>
            ))}
          </div>
          <div className="mt-5 rounded-2xl border border-stone-200 bg-stone-50 p-4 text-sm text-stone-700">
            <p className="font-semibold text-stone-900">Critical findings</p>
            <p className="mt-2 text-2xl font-bold text-stone-900">{criticalFindings}</p>
            <p className="mt-2">0 high findings</p>
          </div>
        </section>
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold text-stone-900">Authorization controls</h2><div className="mt-4 space-y-2">{release.hardening.authorization.controls.map((control) => <div key={control.label} className="flex items-center justify-between rounded-xl border border-stone-200 bg-stone-50 p-3 text-sm"><span>{control.label}</span><StatusPill tone={control.status === "PASS" ? "success" : "danger"}>{control.status}</StatusPill></div>)}</div><p className="mt-4 text-sm text-stone-600">Tests {release.hardening.authorization.testsExecuted} · Passed {release.hardening.authorization.passed} · Failed {release.hardening.authorization.failed}</p></section>
        <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold text-stone-900">AI quality & safety</h2><div className="mt-4 space-y-3">{release.hardening.quality.metrics.map((metric) => <div key={metric.label}><div className="flex justify-between text-sm"><span>{metric.label}</span><strong>{metric.value}{metric.label.toLowerCase().includes("latency") ? "s" : "%"}</strong></div><div className="mt-1 h-2 rounded-full bg-stone-200"><div className="h-2 rounded-full bg-[#a00028]" style={{ width: `${Math.min(100, metric.value)}%` }} /></div></div>)}</div></section>
      </div>
      <section className="overflow-hidden rounded-2xl border border-stone-300 bg-white shadow-sm">
        <div className="flex flex-wrap items-end justify-between gap-3 p-5">
          <div><h2 className="text-xl font-bold text-stone-900">Model & token monitoring</h2><p className="mt-1 text-sm text-stone-600">{release.hardening.monitoring.requests.toLocaleString()} requests · {(release.hardening.monitoring.tokens / 1_000_000).toFixed(2)}M tokens · ${release.hardening.monitoring.estimatedCost.toFixed(2)} estimated cost</p></div>
          <StatusPill tone={release.hardening.monitoring.successRate >= 95 ? "success" : "warning"}>{`${release.hardening.monitoring.successRate}% SUCCESS`}</StatusPill>
        </div>
        {release.hardening.monitoring.modelMetrics.length ? <div className="overflow-x-auto"><table className="min-w-full text-left text-sm"><thead className="bg-stone-50 text-[11px] font-bold uppercase tracking-[0.14em] text-stone-500"><tr><th className="px-4 py-3">Model</th><th className="px-4 py-3">Requests</th><th className="px-4 py-3">Input tokens</th><th className="px-4 py-3">Output tokens</th><th className="px-4 py-3">Avg latency</th><th className="px-4 py-3">Success</th><th className="px-4 py-3">Failures</th><th className="px-4 py-3">Retries</th><th className="px-4 py-3">Cost</th></tr></thead><tbody>{release.hardening.monitoring.modelMetrics.map((metric) => <tr key={metric.model} className="border-t border-stone-200"><td className="px-4 py-3 font-semibold text-stone-900">{metric.model}</td><td className="px-4 py-3">{metric.requests.toLocaleString()}</td><td className="px-4 py-3">{metric.inputTokens.toLocaleString()}</td><td className="px-4 py-3">{metric.outputTokens.toLocaleString()}</td><td className="px-4 py-3">{(metric.avgLatencyMs / 1000).toFixed(2)} s</td><td className="px-4 py-3">{metric.successRate}%</td><td className="px-4 py-3">{metric.failures}</td><td className="px-4 py-3">{metric.retries}</td><td className="px-4 py-3">${metric.estimatedCost.toFixed(2)}</td></tr>)}</tbody></table></div> : <p className="border-t border-stone-200 p-5 text-sm text-stone-600">No model usage has been recorded for this release.</p>}
      </section>
      <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm"><h2 className="text-xl font-bold text-stone-900">Demonstration journey</h2><div className="mt-4 flex flex-wrap gap-2">{release.hardening.regression.steps.map((step) => <span key={step.label} className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">✓ {step.label}</span>)}</div><p className="mt-4 text-sm text-stone-600">{release.hardening.regression.environment} · {release.hardening.regression.duration} · {formatDate(release.hardening.regression.execution)}</p></section>
      {selectedSpan && <SideDrawer title={selectedSpan.stage} eyebrow="Sanitized trace span" onClose={() => setSelectedSpan(null)}><dl className="mt-5 divide-y divide-stone-200 rounded-2xl border border-stone-300 bg-white px-4 text-sm">{[["Trace ID", release.hardening.trace.id], ["Span ID", selectedSpan.id], ["Identifier", selectedSpan.identifier], ["Duration", `${selectedSpan.durationMs} ms`], ["Status", selectedSpan.status], ["Timestamp", formatDate(selectedSpan.timestamp)]].map(([label, value]) => <div key={label} className="flex justify-between gap-4 py-3"><dt className="text-stone-500">{label}</dt><dd className="font-semibold text-stone-900">{value}</dd></div>)}</dl><p className="mt-5 text-xs text-stone-500">Sensitive prompts, payloads, credentials, and tool outputs are excluded.</p></SideDrawer>}
    </div>
  );
}

export default function ReleaseDetailsPage() {
  const { releaseId, tab } = useParams();
  const releaseQuery = useRelease(releaseId ?? "");
  const release = releaseQuery.data;
  const activeTab = tab ?? "overview";
  const [recordedDecision, setRecordedDecision] = useState<{ releaseId: string; decision: ReleaseDecision } | null>(null);
  const [showDecisionModal, setShowDecisionModal] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [notice, setNotice] = useState("");
  const canApproveRelease = (isDeliveryMockMode() || import.meta.env.MODE === "test") && releaseId === "rel-001";

  if (releaseQuery.isLoading) return <main className="min-h-full bg-[#faf8f5] p-8 text-stone-600">Loading release…</main>;
  if (!release) return <main className="min-h-full bg-[#faf8f5] p-5 text-[#202020] md:p-8"><nav className="text-sm"><Link to="/releases" className="font-medium text-[#a00028]">Releases</Link></nav><section className="mt-8 rounded-2xl border border-stone-300 bg-white p-8 text-center"><h1 className="text-2xl font-bold text-stone-900">Release not found</h1><p className="mt-3 text-stone-600">The requested release does not exist or you do not have access to it.</p><Link to="/releases" className="mt-5 inline-flex rounded-xl bg-[#a00028] px-4 py-2 text-sm font-semibold text-white">Back to Releases</Link></section></main>;

  const displayRelease = recordedDecision?.releaseId === release.id ? { ...release, currentDecision: recordedDecision.decision, decisionHistory: [{ id: `local-${recordedDecision.decision.timestamp}`, ...recordedDecision.decision }, ...release.decisionHistory] } : release;
  const refreshAssessment = () => { setIsRefreshing(true); setNotice(""); window.setTimeout(() => { setIsRefreshing(false); setNotice("Release readiness assessment refreshed."); }, 500); };

  const tabs = [
    { id: "overview", label: "Overview", path: `/releases/${release.id}` },
    { id: "readiness", label: "Readiness", path: `/releases/${release.id}/readiness` },
    { id: "release-notes", label: "Release Notes", path: `/releases/${release.id}/release-notes` },
    { id: "evidence", label: "Evidence", path: `/releases/${release.id}/evidence` },
    { id: "risks", label: "Risks & Blockers", path: `/releases/${release.id}/risks` },
    { id: "decisions", label: "Decisions", path: `/releases/${release.id}/decisions` },
    { id: "hardening", label: "Hardening", path: `/releases/${release.id}/hardening` },
  ];

  const renderContent = () => {
    switch (activeTab) {
      case "readiness":
        return <ReleaseReadiness release={displayRelease} canApproveRelease={canApproveRelease} onRecordDecision={() => setShowDecisionModal(true)} />;
      case "evidence":
        return <ReleaseEvidence release={displayRelease} />;
      case "release-notes":
        return <ReleaseNotesPage release={displayRelease} />;
      case "risks":
        return <ReleaseRisks release={displayRelease} />;
      case "decisions":
        return <ReleaseDecisions release={displayRelease} />;
      case "hardening":
        return <ReleaseHardening release={displayRelease} />;
      default:
        return <ReleaseOverview release={displayRelease} />;
    }
  };

  return (
    <main className="min-h-full bg-[#faf8f5] p-5 text-[#202020] md:p-8">
      <nav className="mb-5 flex items-center gap-2 text-sm text-stone-500">
        <Link to="/releases" className="font-medium text-stone-600 hover:text-stone-900">Releases</Link>
        <ChevronRight className="h-4 w-4" />
        <Link to={`/releases/${release.id}`} className="font-semibold text-stone-900 hover:text-[#a00028]">{release.name}</Link>
        {activeTab !== "overview" && <><ChevronRight className="h-4 w-4" /><span className="font-semibold capitalize text-stone-900">{activeTab === "risks" ? "Risks & Blockers" : activeTab === "release-notes" ? "Release Notes" : activeTab}</span></>}
      </nav>

      <header className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-[#a00028]">Release workspace</p>
          <h1 className="mt-2 font-display text-4xl font-bold text-stone-900">{release.name}</h1>
          <p className="mt-2 text-sm text-stone-600">Production release</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-stone-700">
            <span className="font-semibold text-stone-900">{release.environment}</span>
            <span className="ml-2 text-stone-500">Target: {formatShortDate(release.targetDate)}</span>
          </div>
          <button type="button" onClick={refreshAssessment} disabled={isRefreshing} className="inline-flex items-center gap-2 rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700 disabled:opacity-60"><RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} /> {activeTab === "readiness" ? "Refresh Assessment" : "Refresh"}</button>
          {canApproveRelease && <button type="button" onClick={() => setShowDecisionModal(true)} className="rounded-xl bg-[#a00028] px-4 py-2.5 text-sm font-semibold text-white">Record Decision</button>}
        </div>
      </header>

      <div className="mt-6 rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-stone-500">Release status</p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <StatusPill tone="success">{release.lifecycle}</StatusPill>
              <StatusPill tone="purple">{release.recommendation}</StatusPill>
            </div>
          </div>
          <div className="grid gap-x-5 gap-y-2 text-sm text-stone-600 sm:grid-cols-2 lg:grid-cols-3">
            <div><span className="font-medium text-stone-900">Release ID:</span> {release.releaseId}</div>
            <div><span className="font-medium text-stone-900">Version:</span> {release.version}</div>
            <div><span className="font-medium text-stone-900">Environment:</span> {release.environment}</div>
            <div><span className="font-medium text-stone-900">Owner:</span> {release.releaseOwner}</div>
            <div><span className="font-medium text-stone-900">Target:</span> {formatDate(release.targetDate)}</div>
            <div><span className="font-medium text-stone-900">Change:</span> {release.changeReference}</div>
            <div><span className="font-medium text-stone-900">Type:</span> {release.releaseType}</div>
            <div><span className="font-medium text-stone-900">Phase:</span> {release.phase}</div>
          </div>
        </div>
      </div>

      <nav className="mt-6 flex flex-wrap gap-2 border-b border-stone-300 pb-3">
        {tabs.map((tab) => (
          <NavLink
            key={tab.id}
            to={tab.path}
            className={({ isActive }) => `rounded-xl px-3 py-2 text-sm font-semibold transition ${isActive ? "bg-[#a00028] text-white" : "border border-stone-300 bg-white text-stone-700"}`}
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-6">{renderContent()}</div>
      {notice && <div className="fixed bottom-5 right-5 z-50 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800 shadow-lg" role="status">{notice}</div>}
      {showDecisionModal && <RecordDecisionModal release={displayRelease} onClose={() => setShowDecisionModal(false)} onRecord={(decision) => { setRecordedDecision({ releaseId: release.id, decision }); setShowDecisionModal(false); setNotice(`Decision recorded successfully: ${decision.decision}`); }} />}
    </main>
  );
}
