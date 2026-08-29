# AX-JIRA-01 Jira Intelligence Agent

The Jira Intelligence Agent uses the existing governed runtime: request
understanding, reconciliation, capability resolution, routing, planning, managed
execution, evidence response, and audited approval. It is not a parallel chat
endpoint or a direct model-to-Jira connection.

The current slice supports project discovery, filtered issue search, issue read,
metadata/transitions, and five approval-marked actions. Search filters compose
deterministically. Raw JQL policy is documented in
[jira-jql-security.md](jira-jql-security.md), and live evidence in
[jira-evidence-and-citations.md](jira-evidence-and-citations.md).

The comprehensive target additionally requires boards, sprints, history, epics,
versions, dependencies, deterministic metrics, forecasts, comparisons, reports,
ceremonies, personal work, and governed proposals. Unknown or unauthorized data
must remain unknown.

Jira Cloud REST API v3 and Agile API v1 are the only repository-evidenced target.
Jira Data Center is not qualified. See
[AX-JIRA-01-outcome.md](AX-JIRA-01-outcome.md) for open gates.
