from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "authenticated": True,
        "user": {
            "sub": user.get("sub"),
            "username": user.get("username"),
            "client_id": user.get("client_id"),
            "token_use": user.get("token_use"),
            "scope": user.get("scope"),
        },
    }
