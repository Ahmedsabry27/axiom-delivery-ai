import os

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.cognito import verify_token
from app.auth.e2e import verify_e2e_token

security = HTTPBearer(auto_error=False)


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
            return verify_e2e_token(credentials.credentials)
        return verify_token(credentials.credentials)

    except Exception:  # noqa: BLE001 - authentication boundary returns a safe error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token",
        ) from None
