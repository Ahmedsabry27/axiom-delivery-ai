# AX-H04 Remediation Report

Date: 2026-08-20

## Outcome

**INCOMPLETE — NO-GO remains authoritative.**

This remediation pass closes PRR-P0-01 and PRR-P0-02, implements the persisted
Release API/UI boundary required by PRR-P0-03, and fixes the governed runtime
defects behind PRR-P0-04. The release cannot be declared ready until the
remaining authenticated browser, authorization, operational, dependency-audit,
and provenance gates are executed successfully.

## Implemented

- Centralized delivery-data mode parsing. API mode is the default; invalid and
  production mock configuration fails closed.
- Corrected the Portfolio KPI type model so strict TypeScript succeeds.
- Added tenant-scoped `/api/releases` list/detail/create/update/decision
  endpoints backed by `DeliveryRelease`, with optimistic record versions,
  immutable audit events, and explicit mutation permissions.
- Converted Releases list, detail, readiness and notes routing to the persisted
  API in non-mock mode. Development fixtures are loaded only in development and
  are absent from the production artifact.
- Corrected managed-agent execution across three contract boundaries:
  tenant agents may resolve global native tools, string conversation IDs are
  normalized to UUIDs, and server-resolved effective tool permissions are
  carried into execution.
- Added a regression test proving a tenant-published agent can execute the
  global native deployment-report tool through a string conversation ID.

## Validation evidence

| Gate | Result |
|---|---|
| Frontend strict TypeScript | PASS |
| Frontend ESLint | PASS |
| Frontend tests | PASS — 123/123 |
| Frontend production build, mock variable unset | PASS |
| Release fixture chunks in production artifact | PASS — none emitted |
| Production build with mock mode enabled | PASS (negative gate) — rejected by configuration |
| Focused governed-runtime suite | PASS — 37/37 |
| Full backend suite | PASS — 579/579; 391 deprecation warnings |
| Ruff on changed backend paths | PASS |
| Runtime reproduction on disposable E2E database | PASS — deployment report completed and persisted child/tool execution IDs |

## Remaining release blockers

- PRR-P0-03 requires a real authenticated Release journey, including durable
  evidence/notes and approval reload, against the deployed API.
- PRR-P0-04 requires the complete desktop/tablet/mobile governed journey matrix,
  not only the corrected service-level reproduction.
- PRR-P1-01 is blocked: `main` has no commit and every repository path is
  untracked. No trustworthy pre-remediation baseline or rollback tag exists.
- PRR-P1-02 through PRR-P1-08 remain open as recorded in the gap register.
- Online npm and Python dependency audits remain unverified.
- Backup/restore, rollback, outage, key rotation, and on-call rehearsals remain
  unexecuted.
- The pre-existing Chat production chunk remains 857.79 kB (PRR-P2-02).

No P0 or P1 risk has been accepted.
