# Jira JQL security

Jira JQL is a server-side policy boundary. The frontend and the model never call
Jira REST endpoints directly and cannot supply arbitrary REST paths or credentials.

Semantic issue searches are compiled from typed fields (`project_key`,
`issue_type`, `status`, `priority`, and `assignee`) with escaped values and a
maximum of 100 results. Raw JQL is intentionally a smaller supported subset:

- exactly one explicit `project = KEY` clause is required;
- that key must equal the trusted project scope supplied by authorization;
- only the connector's allowlisted issue fields are accepted;
- comments, history predicates, and function calls are rejected;
- the query is capped at 2,000 characters and 100 results;
- unsupported syntax fails closed with `JIRA_JQL_UNSAFE`;
- a project mismatch fails with `INSUFFICIENT_EXTERNAL_PERMISSION`.

The validator is not intended to implement Jira's complete grammar. Syntax that
cannot be proven to be within the supported subset is rejected before any network
request. Jira's own browse and issue-security permissions remain a second control;
returned issues must never be treated as evidence for a different tenant or user.

Live search responses record the normalized executed JQL, enforced result limit,
retrieval timestamp, source mode, and trusted Jira browse links. Credentials and
authorization tokens are never included in this metadata or in audit output.

Known limitation: the current trusted scope is one project key per raw query.
Multi-project JQL requires a future authorization contract capable of passing and
auditing a set of user-authorized project keys.
