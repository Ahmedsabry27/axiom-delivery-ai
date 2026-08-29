# Copilot inline agent activity

`InlineRuntimeActivity` replaces the nested Runtime Orchestrator presentation in the Chat stream. It consumes the same persisted step, tool and action events reconciled by `runtime.reducer.ts`; it does not create timed or inferred progress.

`runtimeActivity.ts` is the centralized safe presentation layer. It deduplicates canonical identities, orders committed sequences, maps internal events to user-facing labels and exposes only safe counts. It never displays prompts, arguments, credentials, queries, stack traces, paths or hidden reasoning.

States use icon plus text: pending, running, completed, waiting, failed, cancelled and skipped. Successful terminal executions collapse to a compact summary and can be expanded. Failures, cancellation, required input and approval remain expanded. Running animation stops for terminal snapshots and is disabled under reduced-motion preferences.

The Activity inspector derives its detailed safe history through the same mapping. SSE delivery, reconnection, hydration, cancellation, continuation, approval and retry remain owned by the existing runtime reducer and `useChat`.
