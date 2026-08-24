# Ceremony checklist templates

AX-CI01 persists 15 canonical ceremony families. A template has a stable family key, monotonically increasing template version, lifecycle, roles, timebox, before/during/after items, required evidence, expected decisions/outputs, and a versioned scoring configuration. A ceremony copies the selected template into `template_snapshot`; later template versions cannot rewrite history.

Checklist states are `NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`, `MISSING`, `BLOCKED`, `EVIDENCE_REQUIRED`, and `NOT_APPLICABLE`. Evidence-required items reject completion without an evidence reference. Not-applicable requires a reason and is excluded from eligible weight.
