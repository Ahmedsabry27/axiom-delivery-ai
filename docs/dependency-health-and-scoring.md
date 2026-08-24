# Dependency health and scoring

Health and priority are centralized deterministic calculations with versioned definitions.

Health dimensions are schedule alignment (25), status/progress (20), ownership/acknowledgement (15), evidence freshness (10), downstream impact (15), resolution confidence (10), and review hygiene (5). Bands are green 80–100, amber 60–79, and red 0–59. If the minimum ownership, date, or status inputs are absent, the result is `UNKNOWN`; absent controls are never treated as healthy. Every response includes score, dimensions, calculation time, completeness, limitations, and `dependency-health-v1`.

Priority adds documented points for critical-path membership, late forecast, blocked state, release/milestone/sprint impact, downstream concentration, missing acknowledgement/owner/date, aging, stale evidence, external status, and escalation. The response includes the capped score, `CRITICAL/HIGH/MEDIUM/LOW` band, triggered factors, affected entities, calculation time, and `dependency-priority-v1`. AI confidence never overrides either calculation.

Dates use UTC-aware timestamps and current tenant-visible records. Resolved, closed, and cancelled dependencies are excluded from overdue attention.
