# AX-FIX-02 outcome

## Completion decision

AX-FIX-02 COMPLETE — AX-EP07 ACCEPTANCE UNBLOCKED

## Root cause

The seeded approver identity was correct: same tenant, directly assigned, and granted `approvals.read`, `approvals.read_all`, and `approvals.approve`. The browser helper changed session storage, but the requester `addInitScript` ran again on navigation and restored the requester token. The list and detail 403 messages therefore reflected the requester identity, not the assigned approver. Backend list, detail, and decision predicates were also duplicated, creating future drift risk.

## Authorization change

`ApprovalAuthorizationService` now owns canonical permissions, SQL visibility predicates, relationships, decision assignment, delegation, and response capabilities. List and detail share it; approve/reject/request-changes use its decision rule; delegation adds its dedicated permission rule. Tenant-scoped repository lookups preserve anti-enumeration. Direct user, requester read-only, normalized role/group, delegated user, tenant read-all, and unassigned approval-pool behavior are explicit. Read-all never bypasses decision assignment or separation of duties.

The frontend consumes backend capabilities and renders read-only detail without decision controls. The E2E identity override now survives full navigation. No production authentication bypass was added.

## Validation

- Focused action/auth tests: 14 passed, including assigned-user detail, read without approve, approve without read, role assignment, list/detail consistency, separation of duties, tenant isolation, expiry/staleness, idempotency, and E2E claims.
- Backend Ruff and format: passed across 386 files; Python compilation passed.
- Full backend suite: 534 passed, then 534 passed again.
- Runtime sequencing and Jira continuation regressions are included and passed in both suites.
- Frontend: ESLint and strict TypeScript passed; 33 files / 106 tests passed; production build passed.
- Primary authenticated browser journey: passed requester submission → assigned approver detail → approval → exactly-once internal execution → independent verification → audit → reload persistence.
- Browser negative-security journey: passed self-approval, cross-tenant access, stale/expired approval, missing evidence, and duplicate-execution protections.
- Migration: none required. Existing `assigned_approver_id`, `assigned_role`, `delegated_from`, `delegated_to`, tenant, status, and action-version fields are sufficient. A clean migration to existing head `a1c3e5f7b9d2` and FastAPI startup passed on the disposable browser database.

## Files created

- `backend/app/action_center/authorization.py`
- `docs/approval-authorization-model.md`
- `docs/AX-FIX-02-outcome.md`

## Files modified

- `backend/app/action_center/service.py`
- `backend/app/api/action_center.py`
- `backend/app/agents/application_service.py`
- `backend/tests/test_action_center.py`
- `frontend/src/services/action.service.ts`
- `frontend/src/pages/approvals/ApprovalsPage.jsx`
- `frontend/src/pages/approvals/ApprovalsPage.test.jsx`
- `frontend/e2e-live/action-center-live.spec.ts`

## Remaining limitations

The current delegation schema supports a recorded direct handoff but not validity windows, revocation, or action/risk scope. Those features remain deferred and are not represented as supported capabilities. Approval-detail reads follow the platform's existing audit policy; decisions and denials retain the existing safe audit/error behavior without logging tokens or payloads.

## Exact validation commands

```bash
cd backend
../.venv/bin/ruff check .
../.venv/bin/ruff format --check .
../.venv/bin/python -m compileall -q app tests
../.venv/bin/pytest -q
../.venv/bin/pytest -q

cd ../frontend
npm run validate
E2E_STATE_PATH=/private/tmp/ax_fix02_browser_state.json \
VITE_API_URL=http://127.0.0.1:8011 \
npx playwright test -c playwright.live.config.ts \
e2e-live/action-center-live.spec.ts --project=live-1440
```

## Recommendation

AX-EP07 may be accepted. The runtime sequencing P0 and legitimate-approver authorization P0 are both closed with consecutive full-suite and authenticated-browser evidence.
