# Agent Evaluation

Agent evaluation reuses `EvaluationDataset`, `GovernedModel`, `EvaluationRun`, `EvaluationResult`, and `EvaluationRunnerService`. Agent-scoped endpoints are:

- `GET /api/v1/agents/{agent_id}/evaluations`
- `POST /api/v1/agents/{agent_id}/evaluations`

Runs are tenant scoped, associated with the tested agent version, and recorded in agent activity. Evaluation inputs must be existing governed dataset and model records. The UI exposes persisted history without hidden test cases or evaluator secrets.

Condition: mandatory evaluation thresholds are not yet enforced as a hard publication gate.
