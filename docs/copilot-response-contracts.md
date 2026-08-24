# Copilot response contracts

Structured delivery responses use a versioned envelope containing `type`, `title`, `status`, `confidence`, `findings`, `limitations`, authorized `evidence`, suggested follow-ups, and suggested actions. Supported initial response types are delivery health, sprint health/forecast, release risk/readiness, RAID summary, dependency analysis, executive summary, clarification, and insufficient evidence.

Confidence is 0–100, capped below certainty and forced to zero when no evidence exists. Invalid structured output must degrade to a clear limited text response; it must never invent sources.
