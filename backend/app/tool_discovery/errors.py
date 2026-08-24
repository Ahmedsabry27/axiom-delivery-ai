from app.tool_sdk.errors import ToolSDKError


class DiscoveryError(ToolSDKError):
    code = "DISCOVERY_INVALID_REQUEST"
    status_code = 422


class PolicyInvalid(DiscoveryError):
    code = "POLICY_INVALID"


class PolicyNotFound(DiscoveryError):
    code = "POLICY_NOT_FOUND"
    status_code = 404
