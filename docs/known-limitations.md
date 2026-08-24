# Known limitations

- Several production delivery read endpoints still return synthetic data.
- Milestone and dependency persistence is incomplete.
- One chat-runtime continuation test is intermittent.
- Backend lint/static analysis is not clean; strict TypeScript checking is not established.
- Conversation delivery context and delivery audit linkage are not wired end to end.
- Clean authenticated browser validation and security scans are incomplete.
- The ChatPage bundle exceeds 500 kB.

These limitations include P0 blockers; AX-EP05 must not begin.
