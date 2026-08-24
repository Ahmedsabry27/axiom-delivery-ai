# Agent Versioning

`AgentVersion` is the immutable configuration snapshot. It includes instructions, governed model selection, planner and memory configuration, execution limits, discovery policy, capabilities, author, change note, and publication state.

Draft updates require the aggregate lock version and create the next version. Historical versions are read-only. Rollback must create a new draft from a selected version; it must never rewrite a published row.

AX-DEMO-01 seeds version 1 snapshots for all demonstration agents.
