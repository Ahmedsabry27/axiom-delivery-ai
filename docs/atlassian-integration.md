# Atlassian integration

AX-EP12A groups Jira and Confluence under a reusable Atlassian authorization while retaining independent connector status, scope, mappings, cursor, quality, and lifecycle. Authorization uses server-side OAuth 2.0 authorization code flow, random one-time tenant/user-bound state, and Atlassian's `api.atlassian.com` gateway. A live callback must resolve `accessible-resources`, require explicit Cloud ID selection, and build Jira/Confluence API paths from that ID rather than a submitted hostname.

The checked-in implementation provides deterministic OAuth and connector simulators. Live token exchange, refresh, revocation validation, and sandbox certification remain disabled until non-production client configuration is supplied.
