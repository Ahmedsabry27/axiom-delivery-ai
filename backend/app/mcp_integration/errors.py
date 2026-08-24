from app.tool_sdk.errors import ToolSDKError


class MCPError(ToolSDKError):
    code = "MCP_EXECUTION_FAILED"
    status_code = 502


class MCPServerNotFound(MCPError):
    code, status_code = "MCP_SERVER_NOT_FOUND", 404


class MCPServerDisabled(MCPError):
    code, status_code = "MCP_SERVER_DISABLED", 409


class MCPConnectionFailed(MCPError):
    code, status_code, retryable = "MCP_CONNECTION_FAILED", 502, True


class MCPAuthenticationFailed(MCPError):
    code, status_code = "MCP_AUTHENTICATION_FAILED", 401


class MCPToolNotFound(MCPError):
    code, status_code = "MCP_TOOL_NOT_FOUND", 404


class MCPToolDisabled(MCPError):
    code, status_code = "MCP_TOOL_DISABLED", 409


class MCPResponseTooLarge(MCPError):
    code, status_code = "MCP_RESPONSE_TOO_LARGE", 502


class UnsafeMCPServerURL(MCPError):
    code, status_code = "UNSAFE_MCP_SERVER_URL", 403


class MCPResourceNotFound(MCPError):
    code, status_code = "MCP_RESOURCE_NOT_FOUND", 404


class MCPPromptNotFound(MCPError):
    code, status_code = "MCP_PROMPT_NOT_FOUND", 404
