# Architecture gap analysis

## P0 — deployment or security blocker

- End-to-end transport is not fully hardened: the current ALB listener and CloudFront API origin use HTTP. Add ACM-backed HTTPS at the ALB and restrict/redirect port 80.
- The repository contains active staging resources but no proven separate production Terraform state/account boundary. Establish protected production state and credentials before declaring production infrastructure managed.

## P1 — production-readiness blocker

- ECS desired count is one and RDS is single-AZ; both are single points of failure.
- No WAF, CloudWatch alarms/SNS, CloudTrail, Config, GuardDuty or Security Hub configuration is evidenced.
- Restore capability is configured but recovery rehearsal, measured RTO/RPO and multi-region decision are unverified.
- One NAT gateway serves both app AZs; private AWS service endpoints are absent.
- Durable queue, retry, idempotency and DLQ behavior for large/async connector synchronization is incomplete.
- Tenant isolation is application-enforced; defense-in-depth database row-level security is not evidenced.
- Amplify and Terraform S3/CloudFront represent competing frontend deployment paths.
- External connector scopes, rate limits, webhook verification and approved write-back require provider-by-provider validation.

## P2 — important improvement

- Add OpenTelemetry/X-Ray propagation and correlate request, runtime, provider/tool, DB, audit and deployment identifiers.
- Establish tested performance/load objectives and ECS autoscaling policy.
- Automate data-class retention, evidence archive and audit preservation.
- Add AWS Budgets/cost anomaly alerts alongside application model budgets.
- Consolidate legacy/duplicate service paths and formalize module ownership.
- Record deployment provenance using image digest and frontend artifact manifest, not tags alone.

## P3 — future optimization

- Evaluate EventBridge/SQS only when durable asynchronous workload volume justifies it.
- Evaluate S3 evidence objects, OpenSearch or a vector store only after corpus/search requirements are measured.
- Evaluate ElastiCache only when shared cache or distributed lock requirements are demonstrated.

Mock/fixture leakage is blocked by production configuration validation, but deployment pipelines should continue explicitly setting `VITE_USE_MOCK_DELIVERY_DATA=false` and testing fail-closed behavior.
