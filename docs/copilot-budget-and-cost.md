# Copilot budget and cost

`runtime_execution_service` invokes the database-backed budget enforcement service before provider invocation. It resolves governed models/prices, locks applicable budgets, reserves estimated Decimal-safe cost, blocks hard limits, emits threshold alerts, and settles or releases reservations on terminal paths. Usage records preserve governed model and price versions.
