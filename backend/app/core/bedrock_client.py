from functools import lru_cache

import boto3
from botocore.client import BaseClient

from app.core.config import settings


@lru_cache(maxsize=1)
def get_bedrock_client() -> BaseClient:
    """Create the Bedrock client only when a model call is made."""
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.AWS_REGION,
    )
