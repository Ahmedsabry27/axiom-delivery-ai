from __future__ import annotations

import json
from collections.abc import Generator, Sequence

from app.ai.base import AIProvider
from app.ai.models import AIMessage, AIResponse, AIStreamEvent, AIUsage


class DeterministicTestProvider(AIProvider):
    """Paid-API-free provider available only in explicitly enabled E2E mode."""

    def __init__(self, model: str) -> None:
        self.model = model

    def ask(self, messages: Sequence[AIMessage]) -> AIResponse:
        input_tokens = max(1, sum(len(item.content) for item in messages) // 4)
        output_tokens = 24
        system = messages[0].content if messages else ""
        text = "Controlled provider response grounded in authorized persisted evidence."
        if system.startswith("Classify the user's semantic intent"):
            text = json.dumps(
                {
                    "intent": "deployment.report.generate",
                    "domain": "deployment_report",
                    "operation": "generate",
                    "resource": "deployment_report",
                    "confidence": 0.99,
                    "ambiguous": False,
                    "ambiguity_reason": None,
                    "entities": {},
                    "semantic_hints": ["deployment", "report"],
                    "source": "llm",
                    "error_code": None,
                }
            )
        elif system.startswith("Extract only parameter values"):
            values = {
                "project_name": "Atlas",
                "release_version": "1.2",
                "environment": "staging",
                "status": "succeeded",
            }
            text = json.dumps(
                {
                    "intent": "deployment.report.generate",
                    "parameters": {
                        name: {
                            "name": name,
                            "value": value,
                            "value_type": "string",
                            "source": "user_prompt",
                            "confidence": 0.99,
                            "explicit": True,
                            "normalized": False,
                            "original_text": value,
                        }
                        for name, value in values.items()
                    },
                    "unresolved_mentions": [],
                    "warnings": [],
                    "source": "llm",
                    "error_code": None,
                }
            )
        return AIResponse(
            text=text,
            response_id="controlled-e2e-response",
            model=self.model,
            latency_seconds=0.001,
            usage=AIUsage(
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
        )

    def stream(
        self, messages: Sequence[AIMessage]
    ) -> Generator[AIStreamEvent, None, None]:
        response = self.ask(messages)
        yield AIStreamEvent(
            event_type="completed",
            text=response.text,
            response_id=response.response_id,
            model=response.model,
            usage=response.usage,
        )
