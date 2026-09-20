import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Archive, LoaderCircle, Trash2 } from "lucide-react";
import {
  deleteAgent,
  getAgentDeletionImpact,
  lifecycleAgent,
} from "../../services/agentService";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";

export default function AgentDeletionDialog({ agent, open, onOpenChange, onCompleted }) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const impact = useQuery({
    queryKey: ["agent", agent?.id, "deletion-impact"],
    queryFn: () => getAgentDeletionImpact(agent.id),
    enabled: open && Boolean(agent?.id),
    retry: false,
  });

  const data = impact.data;
  const eligible = Boolean(data?.eligible_for_permanent_deletion);
  const canArchive = Boolean(data?.permissions?.archive);
  const canDelete = Boolean(data?.permissions?.delete);
  const canSubmit = eligible ? canDelete : canArchive;

  async function confirm() {
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      if (eligible) {
        await deleteAgent(agent.id);
      } else {
        await lifecycleAgent(agent.id, "archive", agent.lock_version, {
          confirmed: true,
          change_note: "Archived after deletion-impact review",
        });
      }
      await onCompleted?.(eligible ? "deleted" : "archived");
      onOpenChange(false);
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail?.message ||
          requestError.message ||
          "The agent could not be changed.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!submitting) { if (!next) setError(""); onOpenChange(next); } }}>
      <DialogContent className="max-w-lg bg-white text-stone-900" aria-describedby="agent-delete-description">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 font-display text-xl font-bold">
            {eligible ? <Trash2 className="text-red-700" /> : <Archive className="text-[#a00028]" />}
            {eligible ? `Delete “${agent?.name}”?` : `Archive “${agent?.name}”?`}
          </DialogTitle>
          <DialogDescription id="agent-delete-description" className="text-stone-600">
            {impact.isLoading
              ? "Checking published versions, executions and references…"
              : impact.isError
                ? "Deletion eligibility could not be checked. No changes have been made."
                : eligible
                  ? "This permanently removes the unused draft from Axiom while retaining its audit record."
                  : `This agent cannot be permanently deleted because it has lifecycle or reference history. Archiving preserves versions, executions and audit history, and removes it from future runtime routing.`}
          </DialogDescription>
        </DialogHeader>

        {impact.isLoading && (
          <div className="flex items-center gap-2 rounded-xl bg-stone-50 p-4 text-sm text-stone-600" role="status">
            <LoaderCircle className="animate-spin" size={18} /> Checking deletion impact…
          </div>
        )}
        {data && !eligible && (
          <ul className="space-y-1 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
            {(data.reasons || []).map((reason) => <li key={reason}>• {reason}</li>)}
            {data.active_execution_count > 0 && <li>• {data.active_execution_count} active execution record(s) will remain preserved.</li>}
          </ul>
        )}
        {data && !canSubmit && (
          <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            You do not have permission to {eligible ? "delete" : "archive"} this agent.
          </p>
        )}
        {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}

        <DialogFooter className="bg-stone-50">
          <button type="button" disabled={submitting} onClick={() => onOpenChange(false)} className="rounded-xl border border-stone-300 bg-white px-4 py-2 font-semibold disabled:opacity-50">
            Cancel
          </button>
          <button
            type="button"
            disabled={impact.isLoading || impact.isError || !canSubmit || submitting}
            onClick={confirm}
            className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 font-semibold text-white disabled:opacity-50 ${eligible ? "bg-red-700" : "bg-[#a00028]"}`}
          >
            {submitting && <LoaderCircle className="animate-spin" size={16} />}
            {eligible ? "Delete permanently" : "Archive agent"}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
