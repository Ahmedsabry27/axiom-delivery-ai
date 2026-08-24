import httpx
import jwt
from cachetools import TTLCache
from jwt import PyJWK
from jwt.exceptions import PyJWTError

from app.auth.config import (
    CLIENT_ID,
    ISSUER,
    JWKS_URL,
)

# Cache Cognito JWKS for 1 hour
_jwks_cache = TTLCache(maxsize=1, ttl=3600)


def get_jwks():
    if "jwks" not in _jwks_cache:
        response = httpx.get(JWKS_URL, timeout=10)
        response.raise_for_status()
        _jwks_cache["jwks"] = response.json()

    return _jwks_cache["jwks"]


def verify_token(token: str) -> dict:
    """
    Verify an AWS Cognito Access Token.
    """

    try:
        header = jwt.get_unverified_header(token)
        kid = header["kid"]

        jwks = get_jwks()

        key = next(
            (k for k in jwks["keys"] if k["kid"] == kid),
            None,
        )

        if key is None:
            raise ValueError("Public key not found.")

        claims = jwt.decode(
            token,
            PyJWK.from_dict(key).key,
            algorithms=["RS256"],
            issuer=ISSUER,
            options={
                "verify_aud": False,  # Access tokens don't use aud
            },
        )

        if claims.get("token_use") != "access":
            raise ValueError("Invalid token type.")

        if claims.get("client_id") != CLIENT_ID:
            raise ValueError("Invalid client.")

        return claims

    except PyJWTError as ex:
        raise ValueError(f"Invalid token: {ex}") from ex
