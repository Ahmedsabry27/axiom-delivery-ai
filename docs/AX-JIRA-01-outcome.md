# AX-JIRA-01 outcome

Status: incomplete.

This increment adds connector-boundary controls for fail-closed scoped raw JQL and
live Jira evidence metadata. It does not claim the comprehensive Jira Intelligence
Agent definition of done.

## Delivered

- Combined semantic filters compile with `AND` for project, issue type, status,
  priority, and assignee.
- Presentation fields remain separate from predicates, so “with their assignees”
  requests output rather than all assignee values.
- Issue reads support description-only and trusted-link responses.
- Raw JQL requires a trusted matching single-project scope, allowlisted fields,
  bounded length/results, and rejects functions, comments, history operators,
  unsupported fields, and project expansion.
- Live searches and reads include trusted links, UTC retrieval time, source mode,
  freshness, and safe query metadata.

## Still required

- User-to-Jira identity mapping, project grants, issue-security revalidation, and
  field-level authorization.
- Paginated boards, sprints, histories, links, epics, versions, and metadata tools.
- Normalized history/scope/checkpoint/evidence/metric persistence and migration.
- Jira wiring for deterministic metrics, forecasts, comparisons, and reports.
- A canonical published Jira Intelligence Agent and multi-capability planning.
- Complete Action Center proposals, separation of duties, exact diffs, and
  independent Jira read-back verification.
- Full evaluations, frontend result tests, browser journeys, repeated stability
  gates, and live authorization qualification.

Baseline: backend 660 passed; frontend install/lint/type-check/build passed; the
full frontend suite had one timeout whose isolated file then passed. Ruff passed;
format check failed on nine existing modified files.

`AX-JIRA-01 INCOMPLETE — CAPABILITY, SECURITY OR QUALITY GAPS REMAIN`
