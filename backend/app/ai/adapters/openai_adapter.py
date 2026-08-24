from collections.abc import Sequence

from app.ai.models import AIMessage, AIMessageRole


class OpenAIAdapter:
    @staticmethod
    def to_input(
        messages: Sequence[AIMessage],
    ) -> list[dict]:

        input_messages = []

        for message in messages:
            if message.role == AIMessageRole.ASSISTANT:
                content_type = "output_text"
            else:
                # system and user
                content_type = "input_text"

            input_messages.append(
                {
                    "role": message.role.value,
                    "content": [
                        {
                            "type": content_type,
                            "text": message.content,
                        }
                    ],
                }
            )

        return input_messages
