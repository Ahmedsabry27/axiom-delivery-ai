"""
Standardized AI provider exceptions.

The rest of the application should only catch these exceptions,
never provider-specific exceptions (OpenAI, Bedrock, etc.).
"""


class AIProviderError(Exception):
    """
    Base exception for all AI provider errors.
    """

    def __init__(self, message: str):
        super().__init__(message)


class AIAuthenticationError(AIProviderError):
    """
    Authentication or authorization failed.
    Examples:
    - Invalid API key
    - Expired credentials
    - IAM permission denied
    """


class AIRateLimitError(AIProviderError):
    """
    The provider rejected the request due to rate limiting.
    """


class AIModelNotFoundError(AIProviderError):
    """
    The requested model does not exist or is unavailable.
    """


class AIStreamingError(AIProviderError):
    """
    An error occurred while streaming a response.
    """


class AIValidationError(AIProviderError):
    """
    Invalid request sent to the provider.
    Examples:
    - Empty prompt
    - Invalid parameters
    - Unsupported options
    """


class AIConnectionError(AIProviderError):
    """
    Network or connectivity issue communicating with the provider.
    """


class AITimeoutError(AIProviderError):
    """
    The provider did not respond within the configured timeout.
    """


class AIConfigurationError(AIProviderError):
    """
    AI provider configuration is invalid.
    Examples:
    - Missing API key
    - Missing AWS region
    - Missing model identifier
    """


class AIUnknownError(AIProviderError):
    """
    Unexpected provider error that could not be mapped to
    a more specific exception.
    """
