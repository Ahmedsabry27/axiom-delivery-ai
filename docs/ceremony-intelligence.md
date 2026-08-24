# Ceremony Intelligence

Ceremonies extend Meeting Intelligence; `meetings` remain the source event and transcript. Ceremony records bind a source meeting to an immutable template snapshot, tenant scope, delivery scope, checklist responses, separate score snapshots, findings, and themes. Decisions remain `MeetingFinding` records and actions remain governed Action Center proposals.

Routes start at `/meetings/ceremonies`; authenticated APIs start at `/api/ceremonies`. Unknown or cross-tenant identifiers return the same non-enumerating not-found response. AI findings remain suggestions with confidence, evidence, limitations, and review state. No individual performance or speaking-time scoring exists.
