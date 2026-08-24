from app.core.config import settings

AWS_REGION = settings.COGNITO_REGION

USER_POOL_ID = settings.COGNITO_USER_POOL_ID

CLIENT_ID = settings.COGNITO_CLIENT_ID

ISSUER = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{USER_POOL_ID}"

JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
