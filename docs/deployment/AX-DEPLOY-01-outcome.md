# AX-DEPLOY-01 outcome

## Completion decision

AX-DEPLOY-01 IN PROGRESS — STAGING FOUNDATION DEPLOYED

## Executive summary

Approval Gate 1 was explicitly approved. Encrypted, versioned, publicly blocked remote state and the staging AWS foundation were deployed. Application deployment remains pending the first honest Git commit, immutable backend image, migration task, ECS service, and frontend upload.

## Evidence

- Branch: `main`
- Commit SHA: pending; repository still has no commit history at this evidence update
- Remote: `https://github.com/Ahmedsabry27/axiom-delivery-ai.git`; verified empty
- Pull request: unavailable; no baseline commit or branch has been pushed
- AWS account: `594677690649`
- AWS profile: `default`
- AWS region: `eu-west-2`
- Environment: `staging`
- Caller identity: existing local IAM user; not approved for GitHub CI
- GitHub authentication design: OIDC workflow exists; no long-lived CI access keys should be used
- Alembic revision: `d2f4a6c8e0b3`
- Approved staging plan: `41 to add / 0 to change / 0 to destroy`
- Remote-state bootstrap applied: `4 added / 0 changed / 0 destroyed`
- Staging foundation applied: `41 managed resources created`; final CloudFront TLS reconciliation was `0 added / 1 changed / 0 destroyed`
- URLs, image digest, artifact hash: unavailable because nothing was deployed
- Secret scan: Gitleaks directory scan passed with no findings
- Terraform: `1.15.8`; configuration formatted and validated
- Terraform provider: `hashicorp/aws 6.61.0`, locked in `.terraform.lock.hcl`
- State: S3 backend with AES-256 encryption, versioning, public-access blocking, separate `staging/terraform.tfstate` key, and native S3 lockfile
- Plan scope: VPC/subnets/routes/NAT, security groups, private S3 with CloudFront OAC and security headers, immutable ECR, private encrypted RDS PostgreSQL, ECS cluster/task definition and roles, ALB, logs
- Runtime safety fix: the least-privilege ECS task role can read only the RDS-managed database secret
- ECS service: intentionally deferred until the SHA-tagged backend image exists in ECR
- Frontend URL: `https://d18zu5xein60s4.cloudfront.net`
- API URL: `http://axiom-delivery-ai-staging-api-276330216.eu-west-2.elb.amazonaws.com`
- ECR: `594677690649.dkr.ecr.eu-west-2.amazonaws.com/axiom-delivery-ai-staging-backend`
- Frontend bucket: `axiom-delivery-ai-staging-frontend-594677690649`
- Backend qualification: `601/601` tests passed twice
- Frontend qualification: lint, type-check, `130/130` tests, and production build passed twice; requalified after dependency remediation
- Production dependency audit: root and frontend report `0 vulnerabilities`
- Dependency remediation: React Router updated to `7.18.2` for the applicable high-severity advisory

## Existing deployment assets

The repository already contains a non-root FastAPI Dockerfile, ECS-oriented health check, GitHub OIDC deployment workflow, disposable PostgreSQL migration workflow, security workflow, Amplify build definition, local PostgreSQL Compose configuration, structured logging, health/readiness endpoints, Alembic migrations, and production configuration guards.

## Target architecture

CloudFront serves a private S3 SPA origin. An internet-facing ALB forwards only application traffic to ECS Fargate tasks in private application subnets. Tasks connect to encrypted RDS PostgreSQL in private database subnets. ECR stores immutable SHA-tagged images. Secrets Manager injects secrets into controlled tasks. CloudWatch receives logs, metrics, dashboards, and alarms. GitHub Actions assumes a repository-scoped AWS role using OIDC.

## Security, migration, and rollback

RDS and ECS tasks remain private; S3 public access is blocked. Database ingress is restricted to the ECS security group. Migration is a separate one-off ECS task and never runs in every application startup. Rollback uses the prior ECS task definition and image digest, the prior versioned S3 artifact, and CloudFront invalidation. Database downgrades are not automatic; recovery uses forward fixes or an explicitly approved snapshot restore.

## Cost categories

Recurring staging costs include NAT, ALB, RDS, CloudFront/S3, ECR, Secrets Manager, CloudWatch, and data transfer. Fargate becomes recurring after the service is enabled. WAF is not in this initial plan. Exact pricing depends on runtime and traffic; the NAT gateway, ALB, and RDS instance are the principal always-on staging costs.

## Known blockers and next action

1. Create and push the honest first baseline after final staged secret and file checks.
2. Build and push a SHA-tagged backend image, then verify its registry scan.
3. Run the one-off Alembic migration and confirm the migration head.
4. Enable the ECS service in a second reviewed zero-destroy plan.
5. Upload the production frontend build, invalidate CloudFront, and execute browser/security journeys.

## Known staging limitation

The generated CloudFront domain uses the CloudFront default certificate. AWS reports that certificate's minimum protocol as `TLSv1` even when Terraform requests `TLSv1.2_2021`, causing a persistent plan diff. Enforcing a minimum TLS policy requires an ACM certificate and custom domain; do not loop-apply this field on the generated domain.
