# Jira evidence and citations

Live Jira issue reads and searches attach machine-produced evidence metadata at
the connector boundary. Issue links are constructed from the configured tenant
connection and Jira-returned issue key; the language model is not trusted to invent
them.

The evidence envelope identifies `jira_live_api`, the UTC retrieval timestamp,
the source or issue browse URL, and freshness `live`. Searches additionally include
the final policy-validated JQL and enforced result limit. Each returned issue gets a
trusted browse URL when Jira supplies a key.

Cached Jira records are not represented as live. Consumers must preserve their
last successful synchronization timestamp, label stale/partial data, and avoid
claiming current status when refresh fails. Missing fields remain unknown; they are
not inferred from summaries or model prose.

Authorization precedes citation generation. A citation is evidence of the returned
record, not proof that a broader project or count is authorized. Credentials,
tokens, comments, worklogs, and restricted fields are excluded unless a dedicated
authorized tool requests them.
