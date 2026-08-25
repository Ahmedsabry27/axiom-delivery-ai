# Non-functional architecture

| Requirement | Current implementation | Evidence | Gap | Target / recommendation | Priority |
|---|---|---|---|---|---|
| Availability | ECS circuit breaker; two subnet sets; single task and single-AZ RDS | Terraform staging | Compute/database SPOFs | Multi-task autoscaling and Multi-AZ RDS after SLO approval | P1 |
| Scalability | Stateless API intent; RDS autoscaling storage | Terraform; runtime services | No ECS autoscaling; long work shares API | Load test; autoscaling; durable queue only where justified | P1 |
| Performance | React code splitting; indexed relational data; bounded tool calls | frontend router; migrations; tool SDK | No accepted latency objectives | Establish proposed SLIs then test representative workloads | P2 |
| Security | Cognito JWT, tenant claims, SGs, secret references, audit | auth/security/Terraform | HTTP ALB origin; no WAF/account controls | End-to-end TLS, WAF, CloudTrail/Config/GuardDuty/Security Hub | P0/P1 |
| Privacy | Redaction and source/evidence controls | `backend/app/security`; docs | Retention/residency acceptance unknown | Approve classification, residency and deletion schedule | P1 |
| Tenant isolation | Tenant claim/group and tenant-scoped services | auth dependencies; tests | Database RLS not evidenced | Continue tests; assess defense-in-depth RLS | P1 |
| Reliability | Runtime leases, recovery, atomic sequences | runtime code/migrations | External sync durability partial | Idempotent retry + queue/DLQ for accepted async flows | P1 |
| Maintainability | Layered modules, migrations, tests and docs | repository | Large router/service surface and legacy paths | Enforce ownership and dependency boundaries | P2 |
| Observability | Structured logs, metrics, health/readiness, audit | logging/metrics/main | Alarms and distributed tracing absent | CloudWatch dashboards/alarms and OTel tracing | P1 |
| Auditability | Append-only/redacted/hash-chained governance audit | audit models/services | External account activity linkage partial | Correlate CloudTrail/deploy evidence with app audit | P1 |
| Accessibility | Shared design system and axe dependency | frontend/docs | Continuous browser evidence not guaranteed | Add protected accessibility gate | P2 |
| Cost management | Model usage ledger and budget enforcement | governance | AWS cost budgets/alerts not evidenced | Add AWS Budgets and cost allocation review | P2 |
| Disaster recovery | RDS backups, S3 versions, ECR retention | Terraform | No measured restore rehearsal or approved RTO/RPO | Approve objectives and run recurring restore exercises | P1 |
| Data retention | Documentation and some log retention | docs; Terraform | Policies not uniformly automated | Automate per-class retention and legal holds | P1 |
| Rate limiting | Provider-specific handling is partial | integrations | No edge/API global rate limit | Add WAF/API throttling and provider budgets | P1 |
| Provider resilience | Safe errors, runtime recovery, provider abstraction | AI/runtime | Circuit breaking/failover policy not complete | Define model/provider fallback and retry budgets | P2 |
| Graceful degradation | Explicit missing evidence and controlled frontend states | delivery/frontend | Some connector/data pages may be unavailable | Standardize health/freshness and partial-data UX | P2 |
