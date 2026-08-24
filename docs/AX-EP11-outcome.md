# AX-EP11 outcome

## Completion decision

AX-EP11 INCOMPLETE

## Executive summary

The Portfolio placeholder now has nine functional routes backed by persisted, tenant-scoped delivery data. Backend-owned health, attention, milestone variance, strategic outcomes, typed Decimal investment snapshots, mixed-currency protection, URL filters/tabs, drill-downs, and existing Copilot/Action links are delivered.

## Architecture and data

- Reused Delivery Portfolio, Programme, Project, Milestone, RAID, Dependency, Release, and Evidence models.
- Added `PortfolioIntelligenceService` plus dedicated portfolio, programme, project, and portfolio-subresource APIs.
- Added forward-only migration `e5a7c9d1f3b6` for strategic outcomes, contribution links, and financial reporting snapshots; no existing columns were repurposed.
- Health is deterministic and versioned as `portfolio-health-v1`.
- Missing values are not treated as zero.

## Validation

- Backend full suite: `580 passed` after implementation.
- Backend Portfolio focused tests: `3 passed`.
- Alembic: one head (`e5a7c9d1f3b6`); a blank SQLite database upgraded through the full chain successfully.
- Ruff checks: passed for changed backend files.
- Frontend lint and strict type check: passed.
- Frontend suite: `38` files / `125` tests passed.
- Frontend production API-mode build: passed with existing Chat/entry chunk-size warnings.
- `git diff --check`: passed.
- Browser verification: blocked because no in-app or extension browser instance was exposed to this session.

## Known limitations

- Entity-level authorization currently relies on tenant scoping rather than a portfolio-specific grant model.
- Evidence/activity detail APIs need deeper integration.
- Export, full pagination, health snapshot persistence, insight dismissal history, and proposal submission from insight cards remain incomplete.
- A second post-change full-suite run, security/secret scans, and desktop/tablet/mobile authenticated browser journeys were not executed.

## Files created

- `backend/app/delivery/portfolio_service.py`
- `backend/app/api/portfolio.py`
- `backend/alembic/versions/e5a7c9d1f3b6_add_portfolio_intelligence_entities.py`
- `backend/tests/test_portfolio_intelligence.py`
- `frontend/src/services/portfolio.service.ts`
- `frontend/src/hooks/usePortfolio.ts`
- `frontend/src/pages/portfolio/PortfolioPages.tsx`
- This documentation set.

## Files modified

- `backend/app/api/delivery.py`
- `backend/app/database/models/delivery.py`
- `backend/app/database/models/__init__.py`
- `backend/app/main.py`
- `frontend/src/app/router.jsx`

## Recommended next step

Add portfolio entity grants and financial permissions, then complete evidence/activity endpoints and the mandatory authenticated browser matrix before changing the completion decision.
