# AX-CHAT-UI-02 outcome

## Completion decision

AX-CHAT-UI-02 FUNCTIONALLY COMPLETE — VISUAL OR STABILITY QUALIFICATION REMAINS

## Executive summary

The Copilot message stream now presents canonical agent activity as compact Axiom-themed rows instead of a nested orchestration dashboard. Conversations, messages, inspector, composer, controls, structured responses, evidence, actions and feedback remain intact.

## Presentation and preserved panels

The original assistant message embedded `RuntimeExecutionCard`, repeated runtime status, agent, duration and workflow metadata, and placed the answer below nested cards. The new presentation uses a small assistant identity, inline activity, and a visually dominant answer container. The Conversations, Chat Messages, and Context/Evidence/Activity panels are preserved.

## Components

- Reused: `ConversationSidebar`, `ChatWindow`, `ChatHeader`, `DeliveryContextBar`, `CopilotInspector`, `StructuredDeliveryResponse`, `MessageFeedback`, composer, `useChat`, and `runtime.reducer.ts`.
- Added: `InlineRuntimeActivity` and the centralized `runtimeActivity.ts` mapping.
- Simplified: `AssistantMessage` and inspector Activity rows.
- Removed from the stream: the `RuntimeExecutionCard` nesting and duplicate execution summary. The legacy component remains in the repository for compatibility/tests but is no longer imported by Chat.

## Runtime mapping and lifecycle

Canonical request, context, planning, agent, tool, evidence, response, input, approval and terminal events map to short safe labels. Rows deduplicate by canonical operation identity and follow committed sequence. Completed executions collapse; waiting, approval, failure and cancellation stay visible. Terminal hydration settles active indicators. The final answer is rendered outside activity.

## Runtime integrity

SSE, persisted hydration, sequence reconciliation, cancellation, waiting-for-input, approval, retry, evidence, proposed actions and conversation restoration were not reimplemented. They continue through the existing reducer and hooks. No synthetic timers or chain-of-thought are exposed.

## Accessibility and responsive behavior

Activity uses semantic regions, polite announcements, assertive failure announcements, icon-plus-text states, keyboard-operable expansion, visible focus, safe truncation and reduced-motion classes. Existing desktop and responsive panel breakpoints remain.

## Validation

Baseline results before implementation: lint passed; strict TypeScript passed; 42 Chat/runtime tests passed; full suite passed with 142 tests; production build passed with mocks disabled.

Focused post-change tests cover safe labels, ordering/deduplication, terminal settlement, running, completion collapse/expand, failure, cancellation, approval, and absence of the Runtime Orchestrator heading.

Post-change results: lint passed with no warnings; strict TypeScript passed; focused Chat/runtime suite passed with 52 tests; the complete frontend suite passed three consecutive times with 46 files and 151 tests per run; the production build passed with mock delivery data disabled. Vite continues to report the pre-existing large-chunk advisory.

## Browser journeys and screenshots

The in-app browser was unavailable in this environment, so authenticated journeys, accessibility automation, and responsive screenshots at 1440/1024/768/375 could not be captured. No screenshots were attached to the task despite the specification referencing two. These are the remaining qualification items.

## Files created

- `frontend/src/components/chat/InlineRuntimeActivity.jsx`
- `frontend/src/components/chat/InlineRuntimeActivity.test.jsx`
- `frontend/src/utils/runtimeActivity.ts`
- `frontend/src/utils/runtimeActivity.test.ts`
- `docs/copilot-chat-ui.md`
- `docs/copilot-inline-agent-activity.md`
- `docs/AX-CHAT-UI-02-outcome.md`

## Files modified

- `frontend/src/components/chat/AssistantMessage.jsx`
- `frontend/src/components/chat/ChatWindow.jsx`
- `frontend/src/components/copilot/CopilotInspector.jsx`
- `frontend/src/components/copilot/CopilotInspector.test.jsx`

## Remaining gaps and recommendation

Run authenticated responsive journeys and capture the required screenshots when a browser session is available. Retain the existing runtime contracts and promote the compact mapping as the only Chat-stream activity presentation.

## Commands executed

`npm ci`; `npm run lint`; `npm run type-check`; focused Vitest commands; `npm test -- --run`; `VITE_USE_MOCK_DELIVERY_DATA=false npm run build`; `git diff --check`.
