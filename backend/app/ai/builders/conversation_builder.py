from collections.abc import Sequence

from app.ai.models import (
    AIMessage,
    AIMessageRole,
)
from app.ai.prompts.system import SYSTEM_PROMPT
from app.models.message import Message


class ConversationBuilder:
    """
    Builds a standardized AI conversation from the stored
    conversation history.
    """

    def build(
        self,
        history: Sequence[Message],
    ) -> list[AIMessage]:

        conversation = [
            AIMessage(
                role=AIMessageRole.SYSTEM,
                content=SYSTEM_PROMPT,
            )
        ]

        for message in history:
            conversation.append(
                AIMessage(
                    role=AIMessageRole(message.role),
                    content=message.content,
                )
            )

        return conversation
