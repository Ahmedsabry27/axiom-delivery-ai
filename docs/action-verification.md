# Action Verification

Successful adapter completion creates one durable `PENDING` verification and moves the action to `VERIFYING`. Verification is a separate permission (`actions.verify`) and the executor cannot verify their own execution.

The RAID verifier independently reads the tenant-scoped system of record using the adapter result's target ID. It records expected result, observed existence/version/reference, timestamped read evidence, human comment and verifier identity. A matching record produces `VERIFIED`; a missing or mismatched target produces `VERIFICATION_FAILED` and attention/notification signals.

Verification records remain associated with the immutable execution attempt. The action detail exposes execution trace IDs and the linked append-only audit events so operators can follow creation, submission, decision, execution and verification without relying on browser state.

Future external adapters must define their own independent read or receipt-validation strategy before policy can expose an execution path.
