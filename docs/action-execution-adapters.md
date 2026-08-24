# Action Execution Adapters

Execution is deny-by-default. A policy can execute only when an action type maps to a named adapter in the explicit server-side allowlist.

## Enabled internal adapters

- `INTERNAL_RAID_CREATE_V1` accepts only columns supported by `DeliveryRAIDItem`, removes identity/audit/scoring fields, validates dates and delegates to `RAIDRepository.create`.
- `INTERNAL_RAID_UPDATE_V1` requires a target RAID ID plus `expected_version`, removes control fields and delegates to `RAIDRepository.update`.

Each attempt persists before/after control metadata, an exact request snapshot, adapter name, actor, trace ID, result summary and sanitized failure. Adapter success moves to verification, not directly to `VERIFIED`.

## Not enabled

Communication drafts, calendar actions, external work-item updates, dependency mutations, owner changes and workflow triggers have no adapter in AX-EP07. Approval does not create one. They remain draft/review outputs until a connector-specific policy, least-privilege permission mapping, idempotency semantics and verification strategy are implemented and tested.

The legacy integration action catalogue moved to `/api/action-catalog`; its former immediate-execution route no longer occupies `/api/actions`.
