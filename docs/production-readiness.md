# Production readiness

AX-H02 status remains **NO-GO**. Persisted delivery APIs, consecutive backend suites, strict TypeScript, dependency audits and the core dependency/milestone migration now pass. Promotion remains blocked by Ruff findings, the missing persisted authenticated delivery browser journey, and incomplete audit-backed Copilot propagation. A production build must set `VITE_USE_MOCK_DELIVERY_DATA=false`; backend production configuration rejects `USE_MOCK_DELIVERY_DATA=true` and schema auto-create.

See [AX-H02-final-gap-closure-report.md](AX-H02-final-gap-closure-report.md) for the authoritative gate evidence.
