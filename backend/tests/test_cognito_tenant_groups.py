import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import dependencies


def credentials() -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="signed-token")


@pytest.mark.asyncio
async def test_signed_tenant_group_becomes_authoritative_tenant_claim(monkeypatch):
    monkeypatch.setattr(
        dependencies,
        "verify_token",
        lambda _token: {
            "sub": "user-1",
            "cognito:groups": ["platform-admin", "tenant_axiom-demo"],
        },
    )

    claims = await dependencies.get_current_user(credentials())

    assert claims["custom:tenant_id"] == "axiom-demo"
    assert claims["cognito:groups"] == ["platform-admin", "tenant_axiom-demo"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "groups",
    [[], ["platform-admin"], ["tenant_alpha", "tenant_beta"]],
)
async def test_missing_or_ambiguous_tenant_group_is_denied(monkeypatch, groups):
    monkeypatch.setattr(
        dependencies,
        "verify_token",
        lambda _token: {"sub": "user-1", "cognito:groups": groups},
    )

    with pytest.raises(HTTPException) as error:
        await dependencies.get_current_user(credentials())

    assert error.value.status_code == 403
    assert error.value.detail["code"] == "TENANT_ASSIGNMENT_REQUIRED"


@pytest.mark.asyncio
async def test_existing_tenant_claim_remains_supported(monkeypatch):
    monkeypatch.setattr(
        dependencies,
        "verify_token",
        lambda _token: {
            "sub": "user-1",
            "custom:tenant_id": "tenant-from-trusted-issuer",
            "cognito:groups": [],
        },
    )

    claims = await dependencies.get_current_user(credentials())

    assert claims["custom:tenant_id"] == "tenant-from-trusted-issuer"
