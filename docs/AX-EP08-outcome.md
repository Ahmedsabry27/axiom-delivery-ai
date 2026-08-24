# AX-EP08 Meeting Intelligence Outcome

## 1. Completion decision

`AX-EP08 INCOMPLETE`

The durable, evidence-backed core slice is implemented and validated, but the epic's full Definition of Done is not met. In particular, analysis currently uses a deterministic grounded extractor rather than the existing AI runtime, and the required Copilot, Command Center, My Day, duplicate-candidate, and complete approval-to-execution browser integrations are not implemented. This decision deliberately does not overstate completion.

## 2. AX-EP07 prerequisite result

`AX-EP07 COMPLETE`

The Phase 1 acceptance gate passed based on AX-FIX-01 and AX-FIX-02 evidence. The formal result is recorded in `docs/AX-EP07-outcome.md`. No AX-EP07 capability was rebuilt.

## 3. Existing functionality reused

- Cognito/E2E authentication claims and tenant identity
- Permission-based authorization
- Audit event persistence and correlation IDs
- AX-EP07 proposed-action and evidence services
- Policy, Approval Center, Action Center, execution, and verification lifecycle
- Existing delivery-domain action types and internal adapters
- Protected React routing, API client, React Query, and Axiom visual language
- Existing forward-only Alembic chain

## 4. Architecture decisions

- Meeting records are durable SQLAlchemy entities and never process-local.
- Every repository query is tenant scoped; cross-tenant object lookup returns the existing anti-enumeration 404 response.
- Routes delegate lifecycle rules to `MeetingService`.
- Transcript parsing is deterministic and treats content as text, never HTML.
- Findings are candidates until a human accepts or edits them.
- Proposals are created through `ActionCenterService` with durable `DeliveryEvidence` referencing the source meeting finding.
- Identical transcript content is deduplicated within one meeting, while stable segment IDs include tenant and meeting scope to avoid cross-meeting primary-key collisions.

## 5. Domain models

Added `Meeting`, `MeetingParticipant`, `MeetingTranscript`, `TranscriptSegment`, `MeetingFinding`, `FindingEvidence`, and `MeetingArtifact`, including composite tenant foreign keys, indexes, unique constraints, version fields, timestamps, evidence offsets, original AI output, and artifact source versions.

## 6. Migration revision

Forward-only revision `b2d4f6a8c0e1`, following `a1c3e5f7b9d2`. A clean SQLite migration from base through the new head passed.

## 7. Meeting states

The domain defines `DRAFT`, `QUEUED`, `PROCESSING`, `EXTRACTED`, `NEEDS_REVIEW`, `PARTIALLY_REVIEWED`, `REVIEWED`, `COMPLETED`, `FAILED`, `CANCELLED`, and `ARCHIVED`, with guarded cancel, review-completion, and archive transitions. Completion rejects mandatory high-impact unreviewed findings. The current synchronous analysis path does not yet persist each intermediate queued/extracted transition independently.

## 8. Finding states

Implemented `UNREVIEWED`, `ACCEPTED`, `EDITED`, `REJECTED`, `MERGED`, and `PROPOSED`. Edits preserve `original_output`; merges remain within the same tenant and meeting; stale versions fail with 409; high-impact rejection requires a reason; rejected findings cannot produce proposals. Synchronization of `SUBMITTED_FOR_APPROVAL`, `APPROVED`, and `EXECUTED` back onto the finding is deferred.

## 9. Transcript parsing

Pasted text/notes, Markdown, VTT, and SRT are supported. Parsing covers canonical ordering, explicit speaker labels, `Unknown speaker`, caption timestamps, empty/malformed content, a 250,000-character limit, unsafe filenames, content hashes, and deterministic segment IDs. Audio/video and live meeting capture remain out of scope.

## 10. AI analysis

The current extractor is deterministic, keyword-based, evidence grounded, idempotent, and persists decisions, actions, risks, issues, dependencies, and open questions. It is explicitly identified as `deterministic-grounded-extractor-v1`. It does not yet invoke OpenAI/Bedrock through the existing runtime, so this is a blocking DoD gap rather than an AI integration claim.

## 11. Evidence validation

Every generated finding has a composite-FK-backed `FindingEvidence` link to a segment plus validated offsets and an excerpt. Proposal creation carries a durable AX-EP07 evidence record. Cross-meeting merge targets and cross-tenant access fail closed. A general structured model-output validator and invalid runtime-output failure path remain deferred with runtime integration.

## 12. Human review

Accept, edit, reject, and merge are domain controlled and version checked. The review workspace shows exact evidence and highlights its stable segment. High-impact findings cannot be bypassed when completing review.

## 13. Duplicate detection

Exact transcript hash deduplication and idempotent analysis are implemented. Delivery-record duplicate candidates, similarity metadata, link/create-separate/dismiss controls, and merge proposals are not implemented.

## 14. AX-EP07 integration

Accepted or edited findings create evidence-backed AX-EP07 proposed actions. Risks/issues map to `CREATE_RAID_ITEM`, dependencies to `CREATE_DEPENDENCY`, actions to `CREATE_DELIVERY_ACTION`, and decisions to `REQUEST_DECISION`. The browser proves durable proposal creation; the pre-existing AX-EP07 suite separately proves approval, execution, verification, and exactly-once behavior. A single Meeting-to-verified-record browser journey remains deferred.

## 15. Copilot integration

Not implemented for authorized meeting context. This is a blocking DoD gap.

## 16. Command Center integration

Not implemented. This is a blocking DoD gap.

## 17. My Day integration

Not implemented. This is a blocking DoD gap.

## 18. Minutes

Versioned meeting minutes are generated and persisted from reviewed findings only. They are not emailed or published. Rich editing and the complete requested section template remain partial.

## 19. Executive summaries

Versioned executive summaries are generated and persisted from reviewed findings only. Rich editing remains partial.

## 20. Security

Authentication, tenant scoping, permission checks, anti-enumeration, explicit processing authorization, safe filename checks, request-size limits, plain-text rendering, high-impact review gates, evidence requirements, and no autonomous external execution are enforced. Transcript bodies are not placed in audit metadata or application log calls.

## 21. Audit and observability

Audit events cover creation, transcript upload, analysis start/completion, finding review, proposal creation, artifact generation, review completion, and archive under the meeting trace. Runtime sequence metrics and model/provider telemetry remain deferred with runtime integration.

## 22. APIs

Implemented list/create/get/update meetings; add/get transcript; analyse/cancel; list/get/edit/accept/reject/merge findings; single and bulk proposal creation; complete review; minutes; executive summary; and archive. List pagination, status filtering, and safe title search are available.

## 23. Frontend routes and components

Implemented protected `/meetings`, `/meetings/new`, `/meetings/:meetingId`, and `/meetings/:meetingId/review` routes. The UI includes API-backed KPIs/list/search/status tabs, authorization-gated creation, persisted detail/findings, evidence review, accept/reject, proposal links, and artifact generation. Advanced filters, file picker, edit/merge controls, duplicate UI, full detail tabs/audit timeline, and Ask Axiom remain incomplete.

## 24. Tests

- Backend Meeting Intelligence: parser formats, stable/scoped segment IDs, persistence, idempotency, evidence, review, proposal, artifacts, tenant isolation, cross-meeting merge rejection, API authorization, completion gating, and archive.
- Frontend: persisted list/attention, processing authorization, evidence display/highlight, and accepted review request.
- Existing action, approval, and atomic-runtime tests were included in focused regression checks.

## 25. Browser results

The authenticated live journey passed at 1440, 1024, 768, and 390 pixel configurations. It created a meeting, confirmed authorization, analysed synthetic content, opened exact evidence, accepted a decision, created a governed proposal, refreshed to prove persistence, rejected cross-tenant access, and confirmed duplicate analysis did not duplicate findings. The required full decision/action/risk/dependency review through approval, execution, minutes, and audit in one journey remains unverified.

## 26. Full validation

- Backend Ruff check and format check: passed.
- Backend full suite after the final segment-ID fix: `539 passed` twice consecutively.
- Frontend lint and strict TypeScript: passed.
- Frontend full suite: first attempt had two pre-existing Release Readiness 5-second timeouts; immediate rerun passed `108 passed`.
- Production build with `VITE_USE_MOCK_DELIVERY_DATA=false`: passed.
- Clean migration through `b2d4f6a8c0e1`: passed.
- Live responsive Meeting Playwright: `4 passed`.

Dependency audits, a dedicated secret-scanner command, configured backend static type checking, upgrade-from-populated-head migration, and complete file-upload/IDOR matrices were not all run. They must not be inferred as passed.

## 27. Files created

- `backend/app/database/models/meeting.py`
- `backend/app/meeting_intelligence/__init__.py`
- `backend/app/meeting_intelligence/service.py`
- `backend/app/api/meetings.py`
- `backend/alembic/versions/b2d4f6a8c0e1_meeting_intelligence.py`
- `backend/tests/test_meeting_intelligence.py`
- `frontend/src/services/meeting.service.ts`
- `frontend/src/pages/meetings/MeetingsPage.jsx`
- `frontend/src/pages/meetings/MeetingsPage.test.jsx`
- `frontend/e2e-live/meeting-intelligence-live.spec.ts`
- `docs/AX-EP08-outcome.md`

## 28. Files modified

- `backend/app/main.py`
- `backend/scripts/seed_live_e2e.py`
- `frontend/src/app/router.jsx`
- `docs/AX-EP07-outcome.md`

## 29. Deferred scope

Teams/Zoom/Meet/Outlook/Calendar integrations, audio/video transcription, voice identification, automatic Jira/ServiceNow updates, messages, calendar events, email, autonomous acceptance, and production deployment remain deferred as required. Runtime-backed AI, duplicate candidates, and cross-surface integrations are also deferred but are blocking gaps for this epic's stated DoD.

## 30. Known limitations

- Deterministic extraction is intentionally conservative and is not an LLM runtime execution.
- No reviewed-history supersession model for re-analysis.
- Proposal workflow status is not projected back to meeting findings.
- No advanced object authorization beyond tenant and permissions.
- Transcript content uses the database text convention; field-level encryption is not present in the project convention.
- Artifact editing, artifact review transitions, and complete audit UI are partial.

## 31. Exact run commands

```text
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/pytest -q backend/tests
.venv/bin/pytest -q backend/tests/test_meeting_intelligence.py backend/tests/test_action_center.py backend/tests/test_atomic_runtime_events.py
cd frontend && npm run lint
cd frontend && npm run type-check
cd frontend && npm test -- --run
cd frontend && VITE_USE_MOCK_DELIVERY_DATA=false npm run build
cd backend && DATABASE_URL=sqlite:////private/tmp/ax_ep08_live2.sqlite ../.venv/bin/alembic upgrade head
cd frontend && E2E_STATE_PATH=/private/tmp/ax_ep08_e2e_state2.json VITE_API_URL=http://127.0.0.1:8000 npx playwright test -c playwright.live.config.ts meeting-intelligence-live.spec.ts
```

## 32. Recommendation for AX-EP09

Finish AX-EP08 before starting a new epic: route structured meeting analysis through the existing runtime and atomic event sequence, add strict output validation and retry/failure semantics, implement authorized duplicate candidates, project proposal workflow status back to findings, integrate Copilot/Command Center/My Day, complete the review and artifact UI, and run the full security plus end-to-end approval/execution journey.
