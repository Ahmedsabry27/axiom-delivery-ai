# AX-PRR-01 Gap Register

| ID | Epic | Requirement / evidence | Severity | Impact and root cause | Required remediation / owner / acceptance test | Blocking |
|---|---|---|---|---|---|---|
| PRR-P0-01 | EP01/02/04/05/06/11 | Frontend delivery services use `VITE_USE_MOCK_DELIVERY_DATA !== "false"`; unset selects mocks | P0 | A production bundle can display demonstration data; configuration defaults open | Default off and fail closed in production; frontend platform; build without variable and prove API requests/no fixtures | Yes |
| PRR-P0-02 | Platform/EP11 | Mandatory strict TypeScript fails in `PortfolioPages.tsx` for KPI `Icon` JSX type | P0 | Mandatory suite/build chain cannot pass; code defect | Correct typed KPI model; frontend owner; three clean full validation passes with mocks disabled | Yes |
| PRR-P0-03 | EP09 | Release UI is substantially fixture-backed and no complete persisted readiness API path was verified | P0 | Core capability lacks proven durable production path | Implement/audit persisted readiness, notes, evidence and approval path; release team; authenticated Journey D | Yes |
| PRR-P0-04 | EP03/07/10 | Latest AX-EP10 completion journey ends runtime execution `FAILED`, not `COMPLETED`; required browser matrix absent | P0 | Governed Copilot-to-cost/audit journey not operationally proven | Root-cause runtime failure and pass persisted desktop/tablet/mobile journey repeatedly; runtime team | Yes |
| PRR-P1-01 | Platform | `main` has no commit and entire repository is untracked | P1 | No provenance, reviewable diff, rollback point, or reproducible release artifact | Establish reviewed initial commit/tag and immutable build provenance; release engineering | Yes |
| PRR-P1-02 | EP08 | Outcome explicitly `AX-EP08 INCOMPLETE`; intermediate transitions/retention gaps documented | P1 | Meeting processing and governance not fully durable/operational | Complete acceptance criteria and persisted live journey; meeting team | Yes |
| PRR-P1-03 | EP10 | Outcome explicitly incomplete and required full cost-control threshold matrix is not browser-proven | P1 | Budget enforcement cannot receive release assurance | Run all thresholds/concurrency/cancellation with audit reconciliation; governance/runtime | Yes |
| PRR-P1-04 | EP11 | Financial-field/entity permissions absent; no Portfolio live journey | P1 | Restricted financial and evidence data access not proven | Add policy enforcement and negative tests/journeys; portfolio/security | Yes |
| PRR-P1-05 | Cross-epic | Journeys A–G are not all implemented and passed as persisted authenticated flows | P1 | Integration regressions may escape unit suites | Create/execute joined evidence-lineage journeys; QA/product teams | Yes |
| PRR-P1-06 | Security | npm audit unavailable due DNS; Python dependency audit tool unavailable | P1 | Vulnerability posture unknown | Run online npm audit and pip-audit in controlled CI, triage high/critical findings; security | Yes |
| PRR-P1-07 | Operations | Backup/restore, rollback, outage, key-rotation and on-call mechanisms not rehearsed | P1 | Recovery and supportability unproven | Execute signed operational drills with RTO/RPO evidence; SRE | Yes |
| PRR-P1-08 | Authorization | Inconsistent tenant claim fallbacks (`"default"`) and incomplete all-entity negative matrix | P1 | Fail-closed/entity non-enumeration consistency unproven | Require tenant claim uniformly and run Journey F; security/backend | Yes |
| PRR-P2-01 | Backend | 388 deprecation warnings in full suite | P2 | Future runtime/library upgrade risk | Remove deprecated UTC and TestClient usages; backend platform | No |
| PRR-P2-02 | Frontend | Chat bundle exceeds 500 kB warning | P2 | Load-time/operability risk without stated target | Define performance budget and split chunk; frontend platform | No |
| PRR-P2-03 | Traceability | Complete original acceptance sources for early epics not found | P2 | Audit completeness and change control weakened | Archive authoritative epic criteria; product operations | No |

No accepted P0 or P1 risks. No confirmed P3 gaps.
