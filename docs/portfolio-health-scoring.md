# Portfolio health scoring

Calculation version: `portfolio-health-v1`.

The backend reuses the centralized delivery health calculator. Weights are project 25%, release 25%, RAID 20%, dependency 15%, and milestone 15%. Available dimensions are reweighted only when at least three dimensions exist; otherwise the result is `UNKNOWN`. Partial evidence is explicitly returned.

Project status inputs map deterministically to scores: completed 100, active 85, planned 70, at risk 45, and blocked 20. Unknown statuses are not treated as zero.

Attention scoring reuses `attention_score` and exposes its impact, urgency, critical-path, and age factors.
