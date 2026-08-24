# Dependency security

All dependency APIs require the existing authenticated identity and derive tenant and actor from that identity. Repository reads, writes, endpoints, evidence, candidates, history, scenarios, and proposals are tenant-scoped. Missing or foreign IDs return safe not-found/forbidden responses, preventing direct-object-reference disclosure.

Internal provider/consumer endpoints must exist in the current tenant. External placeholders require the external flag and cannot contain a foreign tenant record. Duplicate relationships, self-links, unsupported types, invalid lifecycle transitions, unsafe sort keys, excessive pagination, excessive traversal, and cycles are rejected before commit. Updates require the current optimistic version.

Evidence is returned through the existing authorization boundary. Candidate evidence must be persisted and authorized; candidates cannot automatically create relationships. Proposed actions stop before approval or execution. Logs and audit events contain trace IDs and identifiers, not tokens, secrets, source bodies, or chain-of-thought.

Permissions map to existing capability checks for read, create, update, assign, acknowledge, resolve/close, analyse, candidate review, evidence, relationships, and administration. No route performs an external write.

Validation on 2026-08-15 found no secret-pattern matches and `npm audit --omit=dev` reported zero vulnerabilities. `pip-audit` reported `PYSEC-2026-1325` in transitive `ecdsa 0.19.2` with no upstream fix. The application only verifies Cognito JWTs through `python-jose`; it does not call ECDSA signing, key-generation, or ECDH APIs, so the timing-attack finding is classified non-applicable to this code path and retained as a tracked supply-chain limitation.
