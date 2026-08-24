# Copilot streaming events

AX-EP03 preserves `/api/chat/start` and the existing durable runtime SSE subscription. One execution/trace identity is retained across start, progress, continuation, cancellation, and completion.

Delivery metadata may represent progress equivalent to `context.resolved`, `retrieval.started`, `evidence.found`, `analysis.started`, `structured_response.ready`, and `proposed_action.ready`. Existing consumers continue to receive canonical runtime events. Internal prompts and chain-of-thought are never streamed.

```mermaid
flowchart TD
 A[User question] --> B[Resolve context]
 B --> C[Retrieve authorized evidence]
 C --> D[Select capability]
 D --> E[Analyse]
 E --> F[Validate response]
 F --> G[Present answer and sources]
 G --> H[Propose action]
 H --> I[Human review]
```
