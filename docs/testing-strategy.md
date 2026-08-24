# Testing strategy

The release gate requires backend unit/integration/API tests, frontend unit/component tests, lint, Python and TypeScript static analysis, production builds, clean migration tests, security scans, and authenticated browser journeys.

AX-H01 evidence on 2026-08-14: targeted backend 20/20; full backend 504 passed/1 failed; frontend 72/72; frontend ESLint passed; production build passed with a large-chunk warning; clean migration passed; Ruff failed with 505 findings. Because mandatory gates are not all green, the decision is NO-GO.
