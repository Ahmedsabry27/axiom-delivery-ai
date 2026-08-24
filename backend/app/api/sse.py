import json

from app.ai.models import AIStreamEvent


def to_sse(event: AIStreamEvent) -> str:
    payload = {
        "type": event.event_type,
    }

    if event.text:
        payload["text"] = event.text

    if event.response_id:
        payload["response_id"] = event.response_id

    if event.model:
        payload["model"] = event.model

    if event.usage:
        payload["usage"] = {
            "prompt_tokens": event.usage.prompt_tokens,
            "completion_tokens": event.usage.completion_tokens,
            "total_tokens": event.usage.total_tokens,
        }

    if event.metadata:
        payload["metadata"] = event.metadata

    return f"data: {json.dumps(payload)}\n\n"
