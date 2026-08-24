from functools import lru_cache

from openai import OpenAI

from app.core.config import settings


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """Create the OpenAI client only when the provider is actually used."""
    return OpenAI(api_key=settings.OPENAI_API_KEY)
