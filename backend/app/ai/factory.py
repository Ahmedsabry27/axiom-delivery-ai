from __future__ import annotations

from functools import lru_cache

from app.ai.base import AIProvider
from app.ai.governed_provider import GovernedProvider
from app.ai.providers.bedrock_provider import BedrockProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.ai.providers.test_provider import DeterministicTestProvider
from app.core.config import settings


class AIProviderFactory:
    """
    Factory responsible for creating AI provider instances.

    Providers are cached by (provider_name, model) so multiple providers
    and multiple models can coexist without recreating clients on every
    request.
    """

    @staticmethod
    @lru_cache(maxsize=32)
    def get_provider(
        provider_name: str | None = None,
        model: str | None = None,
    ) -> AIProvider:
        """
        Returns an initialized AI provider.

        Args:
            provider_name:
                openai | bedrock

            model:
                Optional model override.

        Returns:
            AIProvider
        """

        provider = (provider_name or settings.AI_PROVIDER).strip().lower()

        if settings.APP_ENV.lower() == "e2e" and settings.E2E_TEST_PROVIDER_ENABLED:
            resolved = DeterministicTestProvider(model or settings.default_ai_model)
        elif provider == "openai":
            resolved = OpenAIProvider(
                model=model or settings.OPENAI_MODEL,
            )
        elif provider == "bedrock":
            resolved = BedrockProvider(
                model=model or settings.BEDROCK_MODEL_ID,
            )
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")
        if settings.BUDGET_ENFORCEMENT_ENABLED:
            return GovernedProvider(resolved)
        return resolved

    @staticmethod
    def clear_cache() -> None:
        """
        Clears cached provider instances.

        Useful in tests or when configuration changes.
        """
        AIProviderFactory.get_provider.cache_clear()
