# Workflow execution

AX-WF01 must hand execution to the canonical runtime so approvals, required-input continuations, budgets, costs, cancellation, retries, audit correlation, and atomic event sequencing remain authoritative.

Normal execution is currently rejected unless a workflow is published. Runtime binding and safe-test isolation are not yet complete; the API returns an explicit `RUNTIME_HANDOFF_REQUIRED` response instead of simulating execution or mutating an external system.
