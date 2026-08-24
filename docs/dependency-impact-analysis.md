# Dependency impact analysis

Impact analysis starts at a persisted dependency edge and performs bounded downstream breadth-first traversal. Direct consumers are separated from indirect entities; typed results identify work items, sprints, milestones, releases, and teams, plus paths, maximum depth, assumptions, limitations, and confidence.

A slip supplies a scenario delta only. The service does not alter dependency, sprint, milestone, release, or work-item dates and does not invent missing duration. A result explicitly reports `readOnly: true` or `authoritativeRecordsChanged: false`. The same authorized graph is used by API, UI, Sprint Intelligence, Command Center, and Copilot.

The calculation stops at the requested/maximum depth, the authorized graph boundary, a disconnected node, or a graph limit. Tenant filtering happens before graph construction, so traversal cannot discover a foreign node or edge.
