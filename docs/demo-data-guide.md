# Connected demonstration data guide

AX-DEMO-01 provides an explicit development/test-only seed command. It writes fictional records through SQLAlchemy into the normal schema; authenticated APIs and API-mode frontend services read those records. Nothing seeds at application startup and no public seed endpoint exists.

## Safety prerequisites

Set `APP_ENV=development` or `test`, `ALLOW_DEMO_SEED=true`, and use the exact tenant `axiom-demo`. Production, staging, missing flags, empty tenants, and other tenant IDs fail closed.

```bash
cd backend
APP_ENV=development ALLOW_DEMO_SEED=true \
  ../.venv/bin/python -m app.seed.demo_data \
  --tenant-id axiom-demo --scenario enterprise-transformation \
  --reference-date 2026-10-06
```

Dry run and validation:

```bash
APP_ENV=development ALLOW_DEMO_SEED=true ../.venv/bin/python -m app.seed.demo_data --tenant-id axiom-demo --dry-run
APP_ENV=development ALLOW_DEMO_SEED=true ../.venv/bin/python -m app.seed.demo_data --tenant-id axiom-demo --validate
```

Exact-tenant reset:

```bash
APP_ENV=development ALLOW_DEMO_SEED=true ../.venv/bin/python -m app.seed.demo_data --tenant-id axiom-demo --reset-demo-tenant --confirm-tenant axiom-demo
```

Run the frontend with `VITE_USE_MOCK_DELIVERY_DATA=false`. The authenticated claim must contain `custom:tenant_id=axiom-demo`; personas use `@demo.axiom.invalid` identifiers and no passwords are stored.
