import os

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.cognito import verify_token
from app.auth.e2e import verify_e2e_token

security = HTTPBearer(auto_error=False)
TENANT_GROUP_PREFIX = "tenant_"


def _with_tenant_claim(claims: dict) -> dict:
    if claims.get("custom:tenant_id"):
        return claims
    tenant_groups = {
        str(group)[len(TENANT_GROUP_PREFIX) :]
        for group in claims.get("cognito:groups", []) or []
        if str(group).startswith(TENANT_GROUP_PREFIX)
        and len(str(group)) > len(TENANT_GROUP_PREFIX)
    }
    if len(tenant_groups) != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TENANT_ASSIGNMENT_REQUIRED",
                "message": "Exactly one Cognito tenant group is required",
            },
        )
    return {**claims, "custom:tenant_id": tenant_groups.pop()}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),  # noqa: B008
):
    if credentials is None:
        environment = os.getenv("APP_ENV", "development").lower()
        if os.getenv("LOCAL_DEMO_AUTH", "").lower() == "true" and environment in {
            "development",
            "test",
        }:
            return {
                "sub": "local-developer",
                "username": "ahmed.sabry",
                "custom:tenant_id": "axiom-demo",
                "email": "ahmedsabry27@outlook.com",
                "name": "Ahmed Sabry",
                "given_name": "Ahmed",
                "family_name": "Sabry",
                "cognito:groups": ["platform-admin"],
                # Existing module authorizers treat an empty legacy permission claim
                # as unrestricted; platform-admin is resolved by newer contexts.
                "permissions": [],
            }
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )

    try:
        if credentials.credentials.startswith("e2e."):
            claims = verify_e2e_token(credentials.credentials)
        else:
            claims = verify_token(credentials.credentials)

    except Exception:  # noqa: BLE001 - authentication boundary returns a safe error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token",
        ) from None
    return _with_tenant_claim(claims)
