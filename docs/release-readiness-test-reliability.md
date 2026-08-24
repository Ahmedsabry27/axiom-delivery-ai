# Release Readiness Test Reliability

## Problem

Two Release Readiness interaction tests exhausted Vitest's existing five-second timeout only when the complete frontend suite ran under parallel JSDOM load. Both passed when run alone and when their file ran alone.

## Root cause

The tests repeatedly used document-wide accessible queries and high-fidelity `userEvent` simulation against the large Release Details DOM. Under worker CPU contention, those synchronous interactions became slow enough to exhaust the timeout. The flow has no React Query request, polling loop, observer, unresolved mutation, fake timer, or asynchronous repository operation.

## Resolution

- Dialog queries are scoped with `within(dialog)`.
- Synchronous form interactions use `fireEvent`; assertions still verify validation, confirmation, status, and persisted decision output.
- A repeated mount/open/unmount regression test verifies dialog cleanup.
- Related Release Notes interactions use the same bounded-query pattern.
- Vitest uses one worker so this JSDOM-heavy suite cannot oversubscribe local CPU. Per-test timeouts were not increased.
- The production decision overlay scrolls on short mobile viewports; browser coverage exposed and now guards this behavior.

## Verification summary

- Former failing tests: 30 consecutive passes each.
- Release Readiness file: 20 consecutive passes (140 test executions).
- Release module: 10 consecutive passes (170 test executions).
- Complete frontend suite: five consecutive passes, 110/110 each.
- Shuffled complete suite: seeds 1701, 2603, and 9107 passed, 110/110 each.
- Desktop, tablet, and mobile Playwright release journeys: 3/3 passed with no page console errors.
- `npm run validate`: lint, strict TypeScript, 110/110 tests, and mocks-disabled build passed.

The Release Readiness screen currently uses synchronous mock release data, so loading, request-failure, and retry states do not exist in this component. No artificial async lifecycle was added merely for a test.
