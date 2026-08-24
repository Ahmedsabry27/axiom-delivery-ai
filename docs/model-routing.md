# Model routing

The registry routing view is a decision preview over existing policy fields. It reports `ALLOW` only for an `ACTIVE` model with configured data classifications and regions; every other state is fail-closed as `BLOCK`. Provider availability, budget, and request-specific policy remain runtime checks. Dedicated weighted routing-rule persistence is not part of this increment.
