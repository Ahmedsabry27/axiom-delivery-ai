# Agent Execution Observability

Agent tests and normal runs use the existing durable execution service and canonical runtime events. The workspace exposes status, agent version, actor, model, selected tools, knowledge sources, continuations, duration, usage, cost, correlation ID, and safe errors.

Cancellation and required-input continuation reuse the runtime APIs. Test mode is persisted and external mutations remain governed or adapted safely. Canonical event ordering and atomic sequence allocation are unchanged by AX-AG01.
