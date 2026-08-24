# Settings hierarchy

Effective values resolve in this order: platform default → tenant/workspace override → permitted module override → user preference. The current implementation persists platform defaults, tenant overrides, and user overrides; module overrides are reserved in the precedence contract but are not yet persisted.

Each response identifies its source, inherited status, lock state, approval requirement, version, and last update. User preferences cannot override settings whose catalogue scopes exclude `user`.
