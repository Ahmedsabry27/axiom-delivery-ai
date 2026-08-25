# Agile percentiles and baselines

Percentiles use the inclusive deterministic percentile implementation in `AgileIntelligenceService`. Empty samples are unknown and a single observation returns that observation. Metric observations preserve period boundaries, source timestamp, metric version, numerator, denominator, evidence references, and missing inputs.

Baselines must be based on comparable persisted periods. Suggested OKR targets are labelled `suggested_target` until a human approves them. Recalculation must create or update an identified period observation rather than silently rewriting history.
