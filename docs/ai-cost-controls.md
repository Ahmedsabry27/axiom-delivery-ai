# AI cost controls

Terminal runtime transitions create one tenant/execution usage-ledger record in the same transaction. The unique constraint prevents duplicate metering. Token counts, price version, currency, and calculated cost are persisted when available; absent usage or pricing stays `null`.

Costs use Python `Decimal` and effective versioned `model_prices`, never binary floating point. Budgets persist tenant/scope/period, soft and hard limits, alert thresholds, currency, and effective dates. The current UI and APIs provide controlled records and honest unavailable forecasts; automated provider-price synchronization and financial chargeback are out of scope.
