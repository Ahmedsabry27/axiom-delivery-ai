# Axiom AI Delivery Copilot

The authenticated `/copilot` route extends the existing conversation and runtime architecture with delivery context, evidence-led structured responses, feedback, and controlled proposed actions. `/chat` redirects to `/copilot`; API chat routes are unchanged.

Supported categories include delivery health/change, sprint and release intelligence, RAID, dependency, action and decision search, reporting, recommendations, and proposed-action generation. The context selector supports organization, portfolio, programme, project, sprint, release, and team. Context is passed through runtime metadata and retained locally for follow-up questions.

Axiom Delivery AI is an independent R&D prototype. Demonstration data is synthetic. The Copilot does not execute external actions in AX-EP03; approval and execution belong to AX-EP07.

Provider/model selection remains configuration-driven through the existing OpenAI and Bedrock abstractions. Local mock delivery mode is controlled by `VITE_USE_MOCK_DELIVERY_DATA`; provider-backed answers require the existing backend configuration.

Run locally with `npm run dev` from `frontend`. Validate with `npm test -- --run` and `npm run build`.

Current limitations: delivery retrieval uses the AX-EP01 contract and synthetic foundations; durable structured-response columns and durable proposal/feedback persistence require a future forward-only migration.
