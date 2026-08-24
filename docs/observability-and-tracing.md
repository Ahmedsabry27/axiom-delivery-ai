# Observability and tracing

Execution, approval, audit, usage, evaluation, and incident records retain their available execution and trace identifiers. The execution detail API presents the persisted runtime timeline, and audit filters support trace and execution correlation. Request middleware continues to emit request IDs and structured duration/status logs.

No external APM product is bundled. Latency and evidence-quality measures remain `null` until persisted telemetry exists. This prevents dashboards from presenting operational guesses as measurements.
