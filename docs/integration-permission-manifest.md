# Integration permission manifest

Version: `2026.08.1`. This manifest covers implemented read paths. Write scopes are not requested because external writes remain approval-controlled adapters without live provider activation.

| Connector | Operation | Direction | Official API | Access | Requested scope | Admin consent | Justification |
|---|---|---|---|---|---|---|---|
| Jira | Read projects/issues/users | Inbound | Jira Cloud REST v3 | Delegated | `read:jira-work`, `read:jira-user` | No | Delivery schema and authorized issue synchronization |
| Confluence | Read spaces/pages | Inbound | Confluence Cloud REST v2 | Delegated | `read:confluence-content.all`, `read:confluence-space.summary` | No | Authorized evidence and space discovery |
| Outlook | Read calendars/events | Inbound | Microsoft Graph `/me/calendars`, `/events` | Delegated | `Calendars.Read`, `User.Read` | No | Meeting schedule synchronization and account confirmation |
| Teams | Read online meetings | Inbound | Microsoft Graph online meetings | Delegated | `OnlineMeetings.Read` | No | Authorized meeting metadata |
| Teams | Read transcripts | Inbound | Microsoft Graph call transcripts | Delegated | `OnlineMeetingTranscript.Read.All` | Yes | Authorized transcript ingestion; feature remains degraded without consent/admin setting |

Granted scopes are compared with this versioned manifest. Missing scopes keep the related operation inactive. Mail, chat, channel history, files, recording binaries, broad organization-wide application access, and write scopes are excluded.
