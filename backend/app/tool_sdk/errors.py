class ToolSDKError(Exception):
    code = "TOOL_EXECUTION_FAILED"
    status_code = 500
    retryable = False

    def __init__(self, message: str = "Tool execution failed", *, fields=None):
        super().__init__(message)
        self.safe_message = message
        self.fields = fields or []


class ToolNotFoundError(ToolSDKError):
    code, status_code = "TOOL_NOT_FOUND", 404


class ToolVersionNotFoundError(ToolSDKError):
    code, status_code = "TOOL_VERSION_NOT_FOUND", 404


class ToolDisabledError(ToolSDKError):
    code, status_code = "TOOL_DISABLED", 409


class InvalidToolInputError(ToolSDKError):
    code, status_code = "INVALID_TOOL_INPUT", 422


class OutputValidationError(ToolSDKError):
    code, status_code = "OUTPUT_VALIDATION_FAILED", 502


class PermissionDeniedError(ToolSDKError):
    code, status_code = "PERMISSION_DENIED", 403


class IntegrationNotConfiguredError(ToolSDKError):
    code, status_code = "INTEGRATION_NOT_CONFIGURED", 424


class IntegrationUnavailableError(ToolSDKError):
    code, status_code, retryable = "INTEGRATION_UNAVAILABLE", 503, True


class ToolTimeoutError(ToolSDKError):
    code, status_code, retryable = "EXECUTION_TIMEOUT", 504, True


class ToolCancelledError(ToolSDKError):
    code, status_code = "EXECUTION_CANCELLED", 499


class RateLimitedError(ToolSDKError):
    code, status_code, retryable = "RATE_LIMITED", 429, True


class UnsafeOperationError(ToolSDKError):
    code, status_code = "UNSAFE_OPERATION_REJECTED", 403


SENSITIVE_KEYS = (
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "connection_string",
    "signed_url",
    "api_key",
    "access_key",
    "private_key",
)


def redact(value):
    if isinstance(value, dict):
        return {
            k: "[REDACTED]"
            if any(x in k.lower() for x in SENSITIVE_KEYS)
            else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    if (
        isinstance(value, str)
        and len(value) > 20
        and ("Bearer " in value or "sig=" in value.lower())
    ):
        return "[REDACTED]"
    return value
