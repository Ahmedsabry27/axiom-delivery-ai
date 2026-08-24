# Sprint health scoring

Version 1.0 weights delivery progress 25%, sprint-goal confidence 20%, blocked work 15%, scope stability 10%, dependency health 10%, backlog readiness 10%, and quality 10%. Available dimensions are reweighted only when at least five dimensions exist. Otherwise health is `UNKNOWN`; missing values are never scored as zero.

Thresholds are GREEN 80–100, AMBER 60–79.99, RED 0–59.99. Dimension values and completeness are returned with the score. Health is deterministic and must not be presented as an AI opinion.

Work-item risk combines blocker age (maximum 32), goal criticality (25), size relative to remaining time (20), dependency exposure (15), and readiness gaps (maximum 10).
