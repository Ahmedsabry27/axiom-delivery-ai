# Approval execution and verification

Approved actions continue through the existing Action Center adapters. Execution uses the existing tenant/action/idempotency-key uniqueness boundary, and verification is stored separately from execution. The workbench exposes action state, attempts, adapter summaries, failures, and correlation references through authorized detail views.

Tests must use controlled internal adapters; this implementation does not add an external mutation path.
