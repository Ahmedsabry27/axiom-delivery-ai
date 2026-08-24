# RAID scoring and hygiene

Scoring is deterministic, explainable, and model-independent.

Risk exposure uses probability values Rare 1, Unlikely 2, Possible 3, Likely 4, Almost Certain 5 and impact values Low 1, Minor 2, Moderate/Medium 3, High 4, Critical 5. Exposure is probability × impact. Bands are Low 1–4, Medium 5–9, High 10–16, and Critical 17–25. Inherent and residual values are stored separately.

Missing or invalid inputs return `UNKNOWN` or `INSUFFICIENT_DATA`; missing probability, impact, owner, or evidence is never converted to zero risk.

Attention factors are additive and capped at 100: Critical exposure +40; High +25; overdue +25; critical path +20; critical issue severity +20; missing owner +15; missing mitigation/resolution +15; stale review +10; due within two days +10; age beyond 30 days +10; stale evidence +5; escalated +5. The API returns the reason list with every score.

Hygiene rules report observed/expected values and a recommended correction without modifying records. They include ownership, due/review dates, mitigation/resolution gaps, missing/stale evidence, overdue items, and closure without rationale. Duplicate screening starts with normalized title similarity, then adds same project, owner, and due-date signals. It reports candidates and reasons but never merges automatically.

Assumption confidence, decision urgency, and action urgency use the same evidence/ownership/date primitives and are described as incomplete where supporting persisted data is absent. Threshold changes must be versioned and regression-tested.
