from abc import ABC, abstractmethod
from collections.abc import Generator, Sequence

from app.ai.models import (
    AIMessage,
    AIResponse,
    AIStreamEvent,
)


class AIProvider(ABC):
    """
    Base interface implemented by every AI provider
    (OpenAI, Bedrock, Claude, Gemini, Azure OpenAI, etc.).
    """

    @abstractmethod
    def ask(
        self,
        messages: Sequence[AIMessage],
    ) -> AIResponse:
        """
        Generate a complete response from a conversation.
        """
        ...

    @abstractmethod
    def stream(
        self,
        messages: Sequence[AIMessage],
    ) -> Generator[AIStreamEvent, None, None]:
        """
        Stream a response from a conversation.
        """
        ...
