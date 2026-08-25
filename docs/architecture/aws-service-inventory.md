# AWS service inventory

| Service | Tier | Repository evidence | Status | Notes |
|---|---|---|---|---|
| VPC, subnets, route tables, IGW, NAT | Initial deployment | `infrastructure/terraform/environments/staging/main.tf` | IMPLEMENTED | Two AZ subnet sets, one NAT gateway. |
| ALB and target group | Initial deployment | same | IMPLEMENTED | Current listener/origin is HTTP; edge supplies external HTTPS. |
| ECS Fargate / ECR | Initial deployment | same | IMPLEMENTED | Desired count one; immutable scanned images. |
| RDS PostgreSQL | Initial deployment | same | IMPLEMENTED | Private, encrypted, single-AZ, 7-day backup. |
| Cognito | Initial deployment | same | IMPLEMENTED | Authorization-code client; tenant group convention. |
| Secrets Manager | Initial deployment | `backend/app/integrations/secrets.py`; Terraform IAM | IMPLEMENTED | DB master secret and tenant-prefixed connector secrets. |
| S3 / CloudFront / OAC | Initial deployment | Terraform | IMPLEMENTED | Private/versioned frontend bucket; Amplify also active. |
| Amplify Hosting | Current deployment alternative | `amplify.yml`; `customHttp.yml` | CONFIGURED_NOT_VERIFIED | Live deployment exists, but not represented in Terraform. |
| CloudWatch Logs / Container Insights | Initial deployment | Terraform | IMPLEMENTED | 30-day backend logs; alarms not defined. |
| Bedrock | Initial AI provider | Terraform IAM; `backend/app/ai/providers/bedrock_provider.py` | IMPLEMENTED | Nova Lite allowlisted in current task role. |
| Route 53 / custom ACM | Production hardening | none | PROPOSED | Required for managed custom domain and end-to-end TLS design. |
| WAF | Production hardening | none | PROPOSED | Edge/API threat filtering. |
| KMS customer-managed keys | Production hardening | none | PROPOSED | Current services use AWS-managed/AES256 encryption. |
| ECS autoscaling / multiple tasks | Production hardening | none | PROPOSED | Remove single task SPOF after load/SLO decisions. |
| Multi-AZ RDS | Production hardening | Terraform currently `multi_az=false` | PROPOSED | Availability improvement. |
| Redundant NAT / VPC endpoints | Production hardening | none | PROPOSED | Resilience and private AWS API access. |
| CloudWatch alarms / SNS | Production hardening | none | PROPOSED | Operational alerting. |
| CloudTrail / Config / GuardDuty / Security Hub | Production hardening | none | PROPOSED | Account-level detection and compliance. |
| AWS Backup | Production hardening | none | PROPOSED | Central policy and restore evidence. |
| EventBridge / SQS / DLQ | Optional scalability | none | PROPOSED | Add only for durable async synchronization. |
| S3 evidence / OpenSearch / vector store | Optional scalability | none | PROPOSED | Add only after retrieval/storage requirements justify them. |
| ElastiCache | Optional scalability | none | PROPOSED | No confirmed distributed-cache/lock requirement today. |
