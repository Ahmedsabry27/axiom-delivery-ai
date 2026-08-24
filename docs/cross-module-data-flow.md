# Cross-module data flow

Command Center, My Day and Sprint Intelligence use `DeliveryReadService` over the same persisted tenant records and shared deterministic sprint calculations. Missing transition history returns empty results and explicit limitations. The test scenario in `backend/tests/test_delivery_cross_module.py` proves blocker propagation across these three modules.

## RAID propagation

`DeliveryRAIDItem` is the authoritative aggregate. `RAIDRepository` controls tenant-scoped writes and `raid_intelligence` controls lifecycle, exposure, attention, hygiene, and duplicates. Command Center consumes the resulting prioritized records; My Day includes owned RAID work and review candidates; Sprint Intelligence includes sprint-linked RAID and lowers goal confidence for a persisted critical sprint risk; RAID Copilot reads the same repository, authorizes linked evidence, and persists a structured response. Proposed interventions reuse `ProposedAction` with a typed `raid_id` and a common trace into append-only audit and RAID history. There is no duplicate cross-module score calculation and no external execution.

## Dependency propagation

`DeliveryDependency` plus typed provider/consumer endpoints is the authoritative graph edge. `DependencyRepository` applies tenant scope and `dependency_intelligence` supplies shared health, priority, graph, critical-path, bottleneck, and impact results. Command Center links dependency attention to `/dependencies/{id}`; My Day includes owned/acknowledgement/review work and detected candidates; Sprint Intelligence selects dependency endpoints for the sprint/work items; RAID opens the same dependency graph record; Dependency Copilot returns the same graph result and can persist only a proposed action. A blocked dependency therefore changes each consumer through shared persisted data rather than copied calculations. Evidence IDs and trace IDs preserve authorization and audit continuity; scenarios remain read-only.
