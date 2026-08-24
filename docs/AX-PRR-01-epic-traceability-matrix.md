# AX-PRR-01 Epic Traceability Matrix

This matrix records material sampled criteria. “Production behavior” describes the actual selected path, not documentation claims.

| Epic / requirement | Status | Frontend | Backend / persistence | Authorization / audit | Tests / browser | Production behavior and gap | Severity |
|---|---|---|---|---|---|---|---|
| EP01 canonical contracts and metrics | Pass | shared types/states | `delivery/domain.py`, `metrics.py`, durable delivery migration | authenticated metadata APIs | foundation tests pass | Real backend foundation | — |
| EP01 no mock leakage | Fail | repository selectors default to mock | backend forbids production mock | N/A | production build not reached | Explicit env omission selects mocks | P0 |
| EP02 executive summaries/My Day | Partial | `/command-center`, `/my-day` | `DeliveryReadService` | tenant claim used; audit partial | component/API tests; no current persisted browser proof | Real API exists, default UI path is mock | P0 |
| EP03 structured Copilot/evidence/action | Partial | `/copilot` | runtime, evidence, feedback, proposal models | auth/audit present | many backend tests; full browser chain not passing | Durable foundations, E2E incomplete | P1 |
| EP04 deterministic Sprint Intelligence | Partial | list/detail routes | sprint service over persisted delivery tables | tenant scoped | sprint tests; live delivery fragment | default UI mock path | P0 |
| EP05 RAID lifecycle/evidence/audit | Partial | `/raid` | RAID models/repository/API, migration `d6b9...` | tenant checks and audit history | focused/live specs exist | persisted mode exists; default UI mock | P0 |
| EP06 dependency graph/lifecycle | Partial | `/dependencies` | dependency models/repository/API, migration `e7c0...` | tenant negative tests/spec | backend and live spec | persisted mode exists; default UI mock | P0 |
| EP07 approval/action control | Pass functional | `/actions`, `/approvals` | durable actions/approvals/verifications, migration `f8d1...` | separation-of-duties tests | action-center live spec exists | No complete release-gate rerun | P1 |
| EP08 meeting extraction/review | Partial | meeting routes | meeting models/service, migration `b2d4...` | tenant negative live spec | outcome explicitly incomplete | intermediate transition durability/retention incomplete | P1 |
| EP09 release readiness/notes | Fail | release routes use fixture modules | delivery release base model only; no complete readiness API family found | approval integration not proven | mocked browser spec | Core production path is fixture-led | P0 |
| EP10 governance models/policies/audit | Pass functional | governance/AI Ops routes | migration `c3e5...`; APIs/services | permissions, SoD and hash-chain tests | backend coverage | Durable governance foundation | P1 until full gate |
| EP10 runtime budgets before invocation | Partial | cost/budget screens | migration `d4f6...`; reservation/settlement guard | override approval + audit | unit tests pass; completion E2E fails | Runtime execution ended FAILED in latest browser evidence | P0 |
| EP11 routes and roll-ups | Partial | all eight routes | tenant-scoped Portfolio service | no financial/entity grant enforcement | 2 focused backend tests; no Portfolio E2E | default UI mock; incomplete authorization | P0/P1 |
| Cross-epic evidence → attention | Not tested | multiple pages | cross-module read service | lineage expected | no complete Journey A proof | No release evidence | P1 |
| Cross-epic Copilot → approval → execution | Fail | Copilot/actions/approvals | runtime/action services | control boundaries exist | latest completion browser journey failed | Required journey incomplete | P0 |
| Tenant-isolation matrix | Partial | direct routes not fully covered | broad tenant filters | negative tests/specs exist | not all entities in one run | Portfolio financial/evidence matrix missing | P1 |
| Operations/recovery | Partial | operations dashboards | health/logging/metrics exist | audit controls exist | no recovery rehearsal | Documentation without external evidence | P1 |

Original requirements are recoverable for EP02, EP05–EP11 and hardening/fix initiatives from repository documents and supplied briefs. Complete original acceptance sources for every EP01–EP04 criterion were not found; traceability is incomplete.
