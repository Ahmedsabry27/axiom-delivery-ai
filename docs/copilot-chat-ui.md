# Copilot Chat UI

The Copilot workspace preserves three areas: persisted conversations on the left, messages and the fixed composer in the centre, and the Context/Evidence/Activity inspector on the right. Workspace, agent, provider, model, runtime health and delivery-context controls remain in the header.

Assistant messages render a small Axiom identity, compact canonical runtime activity, the final answer, structured delivery content, evidence, proposed actions and feedback. Runtime activity and answer content are separate. User messages retain their saved content and Axiom styling.

Desktop retains all three areas. Existing `xl` inspector/sidebar behavior preserves the message-first tablet/mobile experience. Activity labels truncate, controls remain keyboard accessible, progress uses `aria-live`, and motion respects `prefers-reduced-motion`.

Validation commands are `npm run lint`, `npm run type-check`, `npm test -- --run`, and `VITE_USE_MOCK_DELIVERY_DATA=false npm run build` from `frontend/`.
