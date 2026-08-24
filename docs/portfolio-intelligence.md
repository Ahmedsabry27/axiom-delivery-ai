# Portfolio Intelligence

Portfolio Intelligence replaces the Portfolio placeholder with persisted, tenant-scoped executive views.

Routes: `/portfolio`, `/portfolio/programmes`, `/portfolio/programmes/:programmeId`, `/portfolio/projects`, `/portfolio/projects/:projectId`, `/portfolio/investments`, `/portfolio/milestones`, `/portfolio/outcomes`, and `/portfolio/insights`. Detail tabs use the shareable `?tab=` URL parameter.

The frontend uses one cancellable React Query read model at `GET /api/delivery/portfolio`. Dedicated read APIs are also available under `/api/portfolios`, `/api/programmes`, and `/api/projects`, including portfolio subresources. The API derives the tenant from authenticated claims and queries persisted delivery, outcome, and investment records. Empty and missing values remain explicit; production routes contain no fixtures.

Ask Axiom links use the existing Copilot route and include the selected entity in URL context. Proposed actions link to the existing Action Center and remain advisory.
