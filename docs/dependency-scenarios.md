# Dependency scenarios

`POST /api/dependencies/graph/scenarios` runs a reproducible delay scenario against the current authorized graph. Inputs validate the dependency, change, and graph bounds. Baseline and scenario results are compared without changing authoritative records.

Unsaved scenarios exist only in the response. When `save` is explicitly selected, the scenario contract, assumptions, difference, limitations, creator, trace, and timestamps are stored in `delivery_dependency_scenarios` and an audit event is emitted. A saved scenario remains a simulation and cannot execute a recommendation.

The UI labels results as simulation, provides save/discard semantics, and repeats that authoritative dates were not changed. EP06 supports delay-day analysis; richer environment, scope-removal, and multi-scenario comparison remain limitations rather than fabricated calculations.
