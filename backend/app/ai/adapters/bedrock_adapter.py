from collections.abc import Sequence

from app.ai.models import AIMessage, AIMessageRole


class BedrockAdapter:
    """
    Converts provider-agnostic AIMessage objects into the
    Amazon Bedrock Converse API format.
    """

    @staticmethod
    def to_messages(
        messages: Sequence[AIMessage],
    ) -> tuple[str | None, list[dict]]:

        system = None
        bedrock_messages = []

        for message in messages:
            if message.role == AIMessageRole.SYSTEM:
                system = message.content
                continue

            bedrock_messages.append(
                {
                    "role": message.role.value,
                    "content": [
                        {
                            "text": message.content,
                        }
                    ],
                }
            )

        return system, bedrock_messages
