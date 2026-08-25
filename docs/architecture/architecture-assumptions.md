# Architecture assumptions and uncertainties

## Confirmed assumptions

- The Terraform staging environment in `eu-west-2` represents the strongest repository evidence for current AWS infrastructure.
- The backend runs on port 8080 behind an internet-facing ALB; PostgreSQL uses 5432 and is not publicly accessible.
- Production configuration is fail-closed for database, Cognito, CORS, model provider and budget controls.
- Delivery records, runtime state, governance, integrations and audit records share PostgreSQL and are tenant-scoped by application controls.
- External write-back is permitted only through explicit governed adapters; recommendations alone do not mutate external systems.

## Uncertainties

| Topic | Status | Consequence / decision needed |
|---|---|---|
| Amplify versus Terraform S3/CloudFront frontend | UNKNOWN | Select one authoritative production topology and lifecycle. |
| Production account and state separation | CONFIGURED_NOT_VERIFIED | Confirm distinct production account/state and protected environments. |
| SLO, RTO and RPO | UNKNOWN | Obtain business approval before sizing HA/DR. |
| External IdP federation | UNKNOWN | Decide Cognito-native versus enterprise SAML/OIDC federation. |
| Durable async synchronization | PROPOSED | Decide EventBridge/SQS/DLQ semantics, retention and replay. |
| Evidence object/search store | PROPOSED | Confirm whether PostgreSQL remains sufficient or S3/OpenSearch/vector search is justified. |
| Multi-region recovery/data residency | UNKNOWN | Confirm regulatory and business requirements. |
| Live connector scope | PARTIALLY_IMPLEMENTED | Validate sandbox permissions, rate limits, webhooks and write-back per provider. |
| Recovery rehearsals | CONFIGURED_NOT_VERIFIED | Record successful restore tests and measured recovery times. |

Suggested targets in the diagrams are proposals, not accepted requirements.
