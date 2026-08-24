# Workflow management

The Automation workspace is available at `/workflows`. It provides a tenant-scoped catalogue, an eight-step creation wizard, and URL-addressable workflow subpages. New workflows are persisted as drafts. Hard deletion is disabled; retirement is the preservation-safe terminal action.

The current implementation is an incremental management layer over the existing workflow and runtime models. It does not introduce another execution engine.
