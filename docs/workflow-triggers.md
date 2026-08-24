# Workflow triggers

The management UI supports Manual, Scheduled, Domain event, and Approval completion configuration with an explicit timezone. Trigger definitions are persisted as part of an immutable workflow version.

The current delivery does not add a scheduler, message broker, or public webhook. Actual scheduled/event dispatch remains deferred to the platform's existing secure infrastructure.
