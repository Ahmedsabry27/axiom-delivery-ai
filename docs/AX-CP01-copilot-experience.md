# AX-CP01 Copilot experience

The Copilot reuses `ChatPage`, `useChat`, `/api/chat/start`, durable runtime events and SSE reconciliation. Organization routes use authenticated APIs; no browser-generated AI response is permitted. `/chat` remains a safe redirect to `/copilot`.

Routes cover the workspace, new conversation, history, saved insights, evidence, proposed actions, prompt library and feedback. Canonical Action and Approval Centers remain the only execution/approval workbenches.
