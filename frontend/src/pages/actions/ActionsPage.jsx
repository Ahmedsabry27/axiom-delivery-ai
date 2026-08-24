import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, ChevronRight, Clock3, FileCheck2, Plus, ShieldCheck, X } from "lucide-react";
import {
  cancelAction,
  createAction,
  executeAction,
  getAction,
  getActions,
  submitAction,
  verifyAction,
} from "../../services/action.service";

const tabs = [
  ["All", null],
  ["Drafts", ["DRAFT", "CHANGES_REQUESTED"]],
  ["Awaiting approval", ["PENDING_APPROVAL"]],
  ["In flight", ["APPROVED", "QUEUED", "EXECUTING", "VERIFYING"]],
  ["Failed", ["FAILED", "PARTIALLY_EXECUTED", "VERIFICATION_FAILED"]],
  ["Completed", ["VERIFIED", "REJECTED", "CANCELLED", "EXPIRED"]],
];

const tones = {
  LOW: "bg-emerald-50 text-emerald-800 border border-emerald-200",
  MEDIUM: "bg-amber-50 text-amber-800 border border-amber-200",
  HIGH: "bg-orange-100 text-orange-900 border border-orange-200",
  RESTRICTED: "bg-rose-100 text-rose-900 border border-rose-200",
};

const errorText = error => error?.response?.data?.detail?.message || error?.message || "The request could not be completed.";
const formatDate = value => value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "—";

function Badge({ children, tone = "bg-stone-100 text-stone-700 border border-stone-200" }) {
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>{children}</span>;
}

function CreateAction({ onClose, onCreated }) {
  const [form, setForm] = useState({
    action_type: "CREATE_RAID_ITEM",
    title: "",
    description: "",
    target_system: "INTERNAL",
    payload: "{}",
    evidence_ids: "",
  });
  const [jsonError, setJsonError] = useState("");
  const mutation = useMutation({ mutationFn: createAction, onSuccess: onCreated });

  const submit = event => {
    event.preventDefault();
    let payload;
    try {
      payload = JSON.parse(form.payload);
      setJsonError("");
    } catch {
      setJsonError("Payload must be valid JSON.");
      return;
    }

    mutation.mutate({
      action_type: form.action_type,
      title: form.title,
      description: form.description,
      target_system: form.target_system,
      payload,
      evidence_ids: form.evidence_ids.split(",").map(value => value.trim()).filter(Boolean),
      idempotency_key: `ui-${crypto.randomUUID()}`,
    });
  };

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-stone-950/40" role="dialog" aria-modal="true" aria-labelledby="create-action-title">
      <form onSubmit={submit} className="h-full w-full max-w-xl overflow-y-auto border-l border-stone-300 bg-[#faf8f5] p-6 shadow-2xl">
        <div className="flex items-start justify-between">
          <div>
            <h2 id="create-action-title" className="font-display text-2xl font-bold text-stone-900">Propose an action</h2>
            <p className="mt-1 text-sm text-stone-600">The action stays draft until policy and evidence checks pass.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-full p-2 text-stone-600 hover:bg-stone-200"><X /></button>
        </div>

        <div className="mt-7 grid gap-5">
          <label className="grid gap-2 text-sm text-stone-700">
            Action type
            <select value={form.action_type} onChange={event => setForm({ ...form, action_type: event.target.value })} className="rounded-xl border border-stone-300 bg-white p-3 text-stone-900">
              <option>CREATE_RAID_ITEM</option>
              <option>UPDATE_RAID_ITEM</option>
              <option>DRAFT_ESCALATION</option>
              <option>DRAFT_STATUS_REPORT</option>
              <option>SEND_MESSAGE</option>
              <option>CREATE_CALENDAR_EVENT</option>
              <option>TRIGGER_WORKFLOW</option>
            </select>
          </label>

          <label className="grid gap-2 text-sm text-stone-700">
            Title
            <input required value={form.title} onChange={event => setForm({ ...form, title: event.target.value })} className="rounded-xl border border-stone-300 bg-white p-3 text-stone-900" />
          </label>

          <label className="grid gap-2 text-sm text-stone-700">
            Description
            <textarea rows="3" value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} className="rounded-xl border border-stone-300 bg-white p-3 text-stone-900" />
          </label>

          <label className="grid gap-2 text-sm text-stone-700">
            Target system
            <input value={form.target_system} onChange={event => setForm({ ...form, target_system: event.target.value })} className="rounded-xl border border-stone-300 bg-white p-3 text-stone-900" />
          </label>

          <label className="grid gap-2 text-sm text-stone-700">
            Approved payload (JSON)
            <textarea rows="9" spellCheck="false" value={form.payload} onChange={event => setForm({ ...form, payload: event.target.value })} className="rounded-xl border border-stone-300 bg-stone-100 p-3 font-mono text-xs text-stone-900" />
          </label>

          <label className="grid gap-2 text-sm text-stone-700">
            Evidence IDs <span className="text-xs text-stone-500">Comma-separated, tenant-authorized evidence references.</span>
            <input value={form.evidence_ids} onChange={event => setForm({ ...form, evidence_ids: event.target.value })} className="rounded-xl border border-stone-300 bg-white p-3 text-stone-900" />
          </label>
        </div>

        {jsonError && <p role="alert" className="mt-5 text-sm text-rose-600">{jsonError}</p>}
        {mutation.isError && <p role="alert" className="mt-5 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{errorText(mutation.error)}</p>}

        <div className="mt-7 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="rounded-xl border border-stone-300 bg-white px-4 py-2 text-stone-700">Cancel</button>
          <button disabled={mutation.isPending} className="rounded-xl bg-[#a00028] px-4 py-2 font-semibold text-white">{mutation.isPending ? "Creating…" : "Create draft"}</button>
        </div>
      </form>
    </div>
  );
}

function ActionDetail({ actionId, onClose }) {
  const queryClient = useQueryClient();
  const [approver, setApprover] = useState("");
  const [comment, setComment] = useState("");
  const query = useQuery({ queryKey: ["action", actionId], queryFn: () => getAction(actionId) });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["action", actionId] });
    queryClient.invalidateQueries({ queryKey: ["actions"] });
  };

  const transition = useMutation({
    mutationFn: async kind => {
      if (kind === "SUBMIT") return submitAction(actionId, approver);
      if (kind === "EXECUTE") return executeAction(actionId, `execute-${crypto.randomUUID()}`);
      if (kind === "VERIFY") return verifyAction(actionId, comment);
      return cancelAction(actionId, comment);
    },
    onSuccess: refresh,
  });

  const action = query.data;

  return (
    <aside className="fixed inset-0 z-30 flex justify-end bg-stone-950/35" aria-label="Action detail">
      <div className="h-full w-full max-w-2xl overflow-y-auto border-l border-stone-300 bg-[#faf8f5] p-6 shadow-2xl">
        <div className="flex justify-between">
          <Link to="/actions" onClick={onClose} className="text-sm font-medium text-[#a00028]">← All actions</Link>
          <button onClick={onClose} aria-label="Close action" className="rounded-full p-2 text-stone-600 hover:bg-stone-200"><X /></button>
        </div>

        {query.isLoading && <p className="mt-8 text-stone-500">Loading action…</p>}
        {query.isError && <p role="alert" className="mt-8 text-rose-600">{errorText(query.error)}</p>}

        {action && (
          <>
            <div className="mt-6 flex flex-wrap items-center gap-2">
              <Badge tone={tones[action.riskLevel]}>{action.riskLevel}</Badge>
              <Badge tone="bg-stone-100 text-stone-700 border border-stone-200">{action.status.replaceAll("_", " ")}</Badge>
              <span className="text-xs text-stone-500">v{action.version} · policy v{action.policyVersion}</span>
            </div>

            <h2 className="mt-4 font-display text-3xl font-bold text-stone-900">{action.title}</h2>
            <p className="mt-2 text-stone-700">{action.description || "No description provided."}</p>

            <section className="mt-7 rounded-2xl border border-stone-300 bg-white p-5">
              <h3 className="font-semibold text-stone-900">Control summary</h3>
              <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
                <div><dt className="text-stone-500">Action type</dt><dd className="mt-1 text-stone-800">{action.actionType}</dd></div>
                <div><dt className="text-stone-500">Target system</dt><dd className="mt-1 text-stone-800">{action.targetSystem}</dd></div>
                <div><dt className="text-stone-500">Requester</dt><dd className="mt-1 text-stone-800">{action.requesterId}</dd></div>
                <div><dt className="text-stone-500">Expires</dt><dd className="mt-1 text-stone-800">{formatDate(action.expiresAt)}</dd></div>
              </dl>
            </section>

            <section className="mt-5 rounded-2xl border border-stone-300 bg-white p-5">
              <h3 className="flex items-center gap-2 font-semibold text-stone-900"><FileCheck2 size={18} className="text-[#a00028]" /> Evidence ({action.evidence?.length ?? 0})</h3>
              {action.evidence?.length ? (
                <ul className="mt-3 space-y-3">
                  {action.evidence.map(item => (
                    <li key={item.id} className="rounded-xl border border-stone-200 bg-stone-50 p-3">
                      <p className="text-stone-900">{item.title}</p>
                      <p className="mt-1 text-xs text-stone-500">{item.sourceSystem} · captured {formatDate(item.capturedAt)}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-amber-700">No evidence is linked. Submission will fail closed for controlled actions.</p>
              )}
            </section>

            <section className="mt-5 rounded-2xl border border-stone-300 bg-white p-5">
              <h3 className="font-semibold text-stone-900">Approved payload</h3>
              <pre className="mt-3 overflow-x-auto rounded-xl bg-stone-100 p-4 text-xs text-stone-800">{JSON.stringify(action.payload, null, 2)}</pre>
            </section>

            <section className="mt-5">
              <h3 className="font-semibold text-stone-900">Decision and execution history</h3>
              <ol className="mt-3 space-y-3 border-l border-stone-300 pl-4">
                {(action.approvals ?? []).map(item => (
                  <li key={item.id}>
                    <p className="text-sm text-stone-800">Approval {item.status.toLowerCase()}</p>
                    <p className="text-xs text-stone-500">{formatDate(item.createdAt)} · {item.assignedApproverId || "unassigned"}</p>
                  </li>
                ))}
                {(action.executions ?? []).map(item => (
                  <li key={item.id}>
                    <p className="text-sm text-stone-800">Execution {item.status.toLowerCase()} via {item.adapter}</p>
                    <p className="text-xs text-stone-500">Attempt {item.attemptNumber} · trace {item.traceId}</p>
                  </li>
                ))}
              </ol>
            </section>

            <section className="mt-5 rounded-2xl border border-stone-300 bg-white p-5">
              <h3 className="font-semibold text-stone-900">Linked audit trail</h3>
              <ol className="mt-3 space-y-2">
                {(action.auditTrail ?? []).map(item => (
                  <li key={item.id} className="text-sm">
                    <span className="text-[#a00028]">{item.action}</span>
                    <span className="text-stone-500"> · {item.actorId} · {formatDate(item.occurredAt)}</span>
                  </li>
                ))}
              </ol>
            </section>

            {(action.availableTransitions?.length ?? 0) > 0 && (
              <section className="sticky bottom-0 mt-8 rounded-2xl border border-[#a00028]/20 bg-white/95 p-4 shadow-lg backdrop-blur">
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="grid gap-1 text-xs text-stone-600">
                    Assigned approver
                    <input value={approver} onChange={event => setApprover(event.target.value)} className="rounded-lg border border-stone-300 bg-stone-50 p-2 text-sm text-stone-900" />
                  </label>
                  <label className="grid gap-1 text-xs text-stone-600">
                    Transition comment
                    <input value={comment} onChange={event => setComment(event.target.value)} className="rounded-lg border border-stone-300 bg-stone-50 p-2 text-sm text-stone-900" />
                  </label>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {action.availableTransitions.filter(item => item !== "EDIT" && item !== "RETRY").map(item => (
                    <button
                      key={item}
                      disabled={transition.isPending}
                      onClick={() => transition.mutate(item)}
                      className={item === "CANCEL" ? "rounded-lg border border-rose-300 bg-rose-50 px-3 py-2 text-sm text-rose-700" : "rounded-lg bg-[#a00028] px-3 py-2 text-sm font-semibold text-white"}
                    >
                      {item.toLowerCase().replaceAll("_", " ")}
                    </button>
                  ))}
                </div>
                {transition.isError && <p role="alert" className="mt-3 text-sm text-rose-600">{errorText(transition.error)}</p>}
              </section>
            )}
          </>
        )}
      </div>
    </aside>
  );
}

export default function ActionsPage() {
  const { actionId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("All");
  const [creating, setCreating] = useState(false);

  const query = useQuery({ queryKey: ["actions"], queryFn: () => getActions() });
  const statuses = tabs.find(item => item[0] === tab)?.[1];
  const allActions = useMemo(() => query.data?.items ?? [], [query.data]);
  const actions = useMemo(() => allActions.filter(action => !statuses || statuses.includes(action.status)), [allActions, statuses]);
  const counts = useMemo(() => Object.fromEntries(tabs.map(([label, values]) => [label, allActions.filter(item => !values || values.includes(item.status)).length])), [allActions]);

  return (
    <main className="min-h-full bg-[#faf8f5] p-5 text-[#202020] md:p-8">
      <header className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.2em] text-[#a00028]">Human control plane</p>
          <h1 className="font-display mt-2 text-3xl font-bold text-stone-900">Action Center</h1>
          <p className="mt-2 max-w-2xl text-stone-600">Review the complete path from proposal and evidence through approval, controlled execution, and verification.</p>
        </div>

        <div className="flex gap-3">
          <Link to="/approvals" className="rounded-xl border border-stone-300 bg-white px-4 py-2.5 text-sm font-medium text-stone-700">Approval inbox</Link>
          <button onClick={() => setCreating(true)} className="flex items-center gap-2 rounded-xl bg-[#a00028] px-4 py-2.5 text-sm font-semibold text-white"><Plus size={17} />Propose action</button>
        </div>
      </header>

      <section className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-stone-300 bg-white p-4"><ShieldCheck className="text-[#a00028]" /><p className="mt-4 text-2xl font-semibold text-stone-900">{query.data?.total || 0}</p><p className="text-sm text-stone-600">Governed actions</p></div>
        <div className="rounded-2xl border border-stone-300 bg-white p-4"><Clock3 className="text-amber-700" /><p className="mt-4 text-2xl font-semibold text-stone-900">{counts["Awaiting approval"]}</p><p className="text-sm text-stone-600">Awaiting decisions</p></div>
        <div className="rounded-2xl border border-stone-300 bg-white p-4"><AlertTriangle className="text-rose-600" /><p className="mt-4 text-2xl font-semibold text-stone-900">{counts.Failed}</p><p className="text-sm text-stone-600">Need intervention</p></div>
        <div className="rounded-2xl border border-stone-300 bg-white p-4"><CheckCircle2 className="text-emerald-700" /><p className="mt-4 text-2xl font-semibold text-stone-900">{counts.Completed}</p><p className="text-sm text-stone-600">Terminal outcomes</p></div>
      </section>

      <nav className="mt-7 flex gap-1 overflow-x-auto border-b border-stone-300" aria-label="Action views">
        {tabs.map(([label]) => (
          <button key={label} onClick={() => setTab(label)} className={`whitespace-nowrap border-b-2 px-4 py-3 text-sm ${tab === label ? "border-[#a00028] text-stone-900" : "border-transparent text-stone-500"}`}>
            {label}
            <span className="ml-2 rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-700">{counts[label]}</span>
          </button>
        ))}
      </nav>

      <section className="mt-5 overflow-hidden rounded-2xl border border-stone-300 bg-white">
        <div className="hidden grid-cols-[1.5fr_.8fr_.7fr_.8fr_32px] gap-4 border-b border-stone-200 px-5 py-3 text-xs uppercase tracking-wider text-stone-500 md:grid">
          <span>Action</span>
          <span>Risk</span>
          <span>Status</span>
          <span>Updated</span>
          <span />
        </div>

        {query.isLoading && <p className="p-8 text-stone-500">Loading governed actions…</p>}
        {query.isError && <p role="alert" className="p-8 text-rose-600">{errorText(query.error)}</p>}

        {actions.map(action => (
          <button key={action.id} onClick={() => navigate(`/actions/${action.id}`)} className="grid w-full gap-3 border-b border-stone-200 px-5 py-4 text-left last:border-0 md:grid-cols-[1.5fr_.8fr_.7fr_.8fr_32px] md:items-center hover:bg-stone-50">
            <span>
              <strong className="block font-medium text-stone-900">{action.title}</strong>
              <small className="mt-1 block text-stone-500">{action.actionType} · v{action.version}</small>
            </span>
            <span><Badge tone={tones[action.riskLevel]}>{action.riskLevel}</Badge></span>
            <span className="text-sm text-stone-700">{action.status.replaceAll("_", " ")}</span>
            <span className="text-sm text-stone-500">{formatDate(action.updatedAt)}</span>
            <ChevronRight className="text-stone-400" />
          </button>
        ))}

        {!query.isLoading && !actions.length && (
          <div className="p-12 text-center">
            <FileCheck2 className="mx-auto text-stone-400" />
            <p className="mt-3 text-stone-800">No actions in this view</p>
            <p className="mt-1 text-sm text-stone-500">Proposals will appear here with their policy and lifecycle state.</p>
          </div>
        )}
      </section>

      {creating && (
        <CreateAction
          onClose={() => setCreating(false)}
          onCreated={action => {
            setCreating(false);
            queryClient.invalidateQueries({ queryKey: ["actions"] });
            navigate(`/actions/${action.id}`);
          }}
        />
      )}

      {actionId && <ActionDetail actionId={actionId} onClose={() => navigate("/actions")} />}
    </main>
  );
}
