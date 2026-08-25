# Copilot runtime states

The UI adapts canonical runtime states for start, planning, evidence retrieval, running, required input, approval, completion, failure and cancellation. Reload reconnects to durable SSE and reconciles events by canonical sequence. Cancellation and terminal failure must settle or release budget reservations.
