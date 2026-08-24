# Production deployment runbook

This application is deployed as a Vite static frontend and a FastAPI ECS/Fargate
service backed by PostgreSQL. Production startup fails closed when authentication,
database, CORS, or schema-version configuration is missing.

## Required platform configuration

Configure these GitHub Actions secrets:

- `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`, `ECR_REPOSITORY`, `ECS_CLUSTER`,
  `ECS_SERVICE`, `ECS_TASK_DEFINITION`, and `ECS_CONTAINER_NAME`.
- `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, and `COGNITO_CLIENT_ID`.
- `E2E_AUTH_SECRET`: a random value of at least 32 characters used only by the
  disposable CI browser environment. Never reuse a production secret.

Configure these repository variables:

- `DATABASE_SECRET_ARN`: the AWS-managed RDS master-user secret ARN.
- `DATABASE_HOST` and `DATABASE_NAME`.
- `CORS_ALLOWED_ORIGINS`: the exact HTTPS frontend origin; do not use `*`.
- `TRUSTED_HOSTS`: the exact public API hostname.

The ECS task definition must inject `OPENAI_API_KEY` from Secrets Manager or SSM.
The task role needs `secretsmanager:GetSecretValue` for the RDS and application
secrets and `kms:Decrypt` when a customer-managed KMS key is used. ECS tasks must
reach RDS on TCP 5432 and AWS APIs through private endpoints or controlled egress.
The service must use `awsvpc` networking and have the ECS deployment circuit
breaker enabled with automatic rollback. The load balancer health check should
target `/ready`; `/health` is liveness only.

Configure the frontend host with the public `VITE_API_URL`,
`VITE_COGNITO_USER_POOL_ID`, `VITE_COGNITO_CLIENT_ID`, `VITE_COGNITO_DOMAIN`, and
`VITE_AUTH_REDIRECT_URI` values. `amplify.yml` builds from `frontend/` and
`customHttp.yml` supplies production response and immutable-asset cache headers.

## Release procedure

1. Require the security, backend, frontend, disposable-PostgreSQL, and browser
   workflows on the protected `main` branch.
2. Confirm the RDS snapshot/backup policy and test the previous task-definition
   rollback before the first production release.
3. Merge to `main`. The backend deployment builds an immutable SHA image, runs
   `alembic upgrade head` as a one-off ECS task, initializes the governed catalog,
   deploys the task definition, waits for stability, and only then promotes
   `latest`.
4. Deploy the frontend only after the API deployment is healthy.
5. Verify `/health`, `/ready`, authentication, dashboard metrics, Agents list and
   detail, chat, one authorized execution, one denied execution, logs, alarms, and
   audit events.

Local equivalents of the required gates:

```bash
cd backend
.venv/bin/ruff check app/core/config.py app/database/config.py app/database/session.py app/database/migrations.py app/main.py app/security scripts tests/test_production_runtime.py tests/test_main_runtime.py tests/test_live_e2e_seed.py
.venv/bin/mypy --follow-imports=skip app/core/config.py app/database/config.py app/database/session.py app/database/migrations.py app/main.py app/security/headers.py
.venv/bin/pytest -q tests

cd ../frontend
npm ci
npm run lint -- --quiet
npx tsc --noEmit
npm test -- --run
npm run build
```

The real browser gate is `.github/workflows/agents-browser.yml`; it migrates a
disposable PostgreSQL 16 database and runs desktop/mobile tests against the real
backend. Do not substitute fixture-only browser results for this gate.

## Rollback and recovery

- Application rollback: redeploy the last known-good immutable image/task
  definition. The ECS circuit breaker handles failed rollouts automatically.
- Database rollback: migrations are forward-only in normal operation. Restore an
  RDS snapshot for destructive failure. New migrations must follow expand/migrate/
  contract sequencing so the prior application remains compatible during rollout.
- Credential incident: rotate the affected secret, revoke exposed credentials,
  redeploy tasks to force refresh, and review CloudTrail and application audit logs.
- Never run `Base.metadata.create_all()` in production or manually edit
  `alembic_version`.

## Release blockers

A release is prohibited while a secret scanner reports a credential, any required
workflow is red, the disposable PostgreSQL migration/browser job has not passed,
the ECS circuit breaker is disabled, production health alarms are absent, or a
restore/rollback procedure has not been exercised.
