# Copilot page architecture

`/copilot` is the canonical runtime workspace. Supporting pages organize persisted records and never duplicate conversations, evidence, actions, approvals or runtime execution. API cancellation uses `AbortSignal`; loading, empty and safe error states are explicit.
