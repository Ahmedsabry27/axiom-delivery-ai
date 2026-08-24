# Runtime Stability Architecture

`RuntimeExecution` is the authoritative public lifecycle. State changes and
durable sequenced events are committed together. Actively running executions
are owned using database leases, renewed by heartbeats, and reclaimed by a
periodic database-backed recovery sweep after process loss.

## Recovery safety

- Read-only abandoned work may be restarted.
- Persisted successful writes are reused and are not replayed.
- A running non-idempotent external action with an unknown outcome is never
  replayed automatically. The runtime fails with
  `RECOVERY_UNCERTAIN_EXTERNAL_ACTION` for operational review.
- Deadlines and bounded recovery attempts take precedence over restart.
- `lease_owner` plus `attempt` fences stale workers from heartbeats, events,
  external actions, and parent transitions.

## Intentional limitations

- Python stacks are not restored after process loss. Recovery uses only
  persisted request, input, child, and event state.
- There is no external durable work queue. Local asyncio tasks perform work;
  database ownership prevents abandoned executions from remaining active.
- Durable workflow step checkpointing is limited. Only conservatively
  classified computation is restartable.
- Uncertain non-idempotent external actions require operational review.
- Durable SSE uses bounded database polling and sequence cursors.
- Multi-instance recovery exclusivity uses database row locking and fencing.

These are deliberate current-scale constraints, not guarantees of arbitrary
distributed workflow replay.

## Epic 2 intelligence pipeline

Enterprise requests use one downstream-only decision chain:

```text
User request
  -> IntentAnalyzer
  -> ParameterExtractor
  -> ParameterReconciler
  -> MissingFieldResolver
  -> ContinuationInterpreter (only while waiting)
  -> CapabilityResolver
  -> AgentRouter
  -> CapabilityAwarePlanner
  -> execution
```

Each stage persists its authoritative output in `RuntimeExecution.runtime_metadata`.
Recovery reuses those outputs and a validated `execution_plan`; it does not
reclassify, rediscover the primary capability, reroute the agent, or replan an
unchanged request.

### Decision ownership

- `IntentAnalyzer` owns semantic meaning, domain, operation, and resource.
- `ParameterExtractor` owns typed, source-aware candidate values.
- `ParameterReconciler` owns canonical value authority and conflicts.
- `MissingFieldResolver` owns schema completeness and exact unresolved fields.
- `ContinuationInterpreter` maps a reply only to pending fields or cancellation.
- `CapabilityResolver` owns registered executable availability, authorization,
  health, tenant visibility, connection choice, and parameter bindings.
- `AgentRouter` owns published-agent eligibility and deterministic selection.
- `CapabilityAwarePlanner` owns exact task construction, dependency metadata,
  schema binding, side-effect policy, and drift validation.

No downstream component may replace an upstream decision. Simple
single-capability plans are deterministic and make no planner-model call.

### Intelligence metadata and events

The durable metadata sections are `intent_analysis`, `parameter_extraction`,
`parameter_state`, `input_requirements`, `capability_resolution`,
`agent_routing`, and `execution_plan`. Corresponding durable events are emitted
in pipeline order. A waiting continuation updates the same execution and
increments `ParameterState.version` before downstream resolution resumes.

### Intelligence limitations

- There is no multi-intent decomposition or autonomous multi-agent planning.
- Missing capabilities are not synthesized or installed automatically.
- Ambiguous capabilities or agents may stop safely instead of opening a new
  clarification flow.
- Connector-specific dynamic schemas remain authoritative for external field
  validation.
- Intent and extraction quality still depend on configured AI providers; safe
  structured fallbacks are used for malformed or unavailable responses.
- Conversation context is bounded and domain-filtered; this is not an advanced
  memory or knowledge-retrieval architecture.
