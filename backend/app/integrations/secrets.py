from __future__ import annotations

import json
import os
import re
import subprocess
from uuid import uuid4

import boto3  # type: ignore[import-untyped]

from app.integrations.errors import IntegrationError


class SecretProvider:
    """Resolve opaque references. Values are never persisted or returned by APIs."""

    def resolve(self, reference: str | None) -> dict:
        if reference and reference.startswith("simulator://"):
            return {"simulator": True}
        if not reference:
            raise IntegrationError(
                "INVALID_CONFIGURATION", "A credential reference is required", 422
            )
        if reference.startswith("env://"):
            name = reference.removeprefix("env://")
            value = os.getenv(name)
            if not value:
                raise IntegrationError(
                    "INVALID_CONFIGURATION",
                    f"Credential environment variable {name} is not configured",
                    422,
                )
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {"token": value}
            except json.JSONDecodeError:
                return {"token": value}
        if reference.startswith("keychain://"):
            service = reference.removeprefix("keychain://")
            if not re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,200}", service):
                raise IntegrationError(
                    "INVALID_CONFIGURATION",
                    "Invalid Keychain credential reference",
                    422,
                )
            try:
                result = subprocess.run(
                    ["security", "find-generic-password", "-s", service, "-w"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                parsed = json.loads(result.stdout)
            except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
                raise IntegrationError(
                    "INVALID_CONFIGURATION",
                    "The Jira credential is unavailable in macOS Keychain",
                    422,
                ) from exc
            if not isinstance(parsed, dict):
                raise IntegrationError(
                    "INVALID_CONFIGURATION", "Invalid Keychain credential format", 422
                )
            return parsed
        if reference.startswith("aws-secrets://"):
            secret_id = reference.removeprefix("aws-secrets://")
            response = boto3.client(
                "secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-1")
            ).get_secret_value(SecretId=secret_id)
            value = response.get("SecretString")
            if not value:
                raise IntegrationError(
                    "INVALID_CONFIGURATION",
                    "The credential secret has no string value",
                    422,
                )
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise IntegrationError(
                    "INVALID_CONFIGURATION",
                    "The credential secret must contain a JSON object",
                    422,
                )
            return parsed
        raise IntegrationError(
            "INVALID_CONFIGURATION", "Unsupported credential reference scheme", 422
        )

    def revoke(self, reference: str | None) -> None:
        """Remove a managed secret when supported; simulator references contain no value."""
        if not reference or reference.startswith(("env://", "simulator://")):
            return
        if reference.startswith("keychain://"):
            subprocess.run(
                [
                    "security",
                    "delete-generic-password",
                    "-s",
                    reference.removeprefix("keychain://"),
                ],
                check=False,
                capture_output=True,
                timeout=10,
            )
            return
        if reference.startswith("aws-secrets://"):
            boto3.client(
                "secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-1")
            ).delete_secret(
                SecretId=reference.removeprefix("aws-secrets://"),
                RecoveryWindowInDays=7,
            )

    def store_keychain(self, service: str, account: str, value: dict) -> str:
        if not re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,200}", service):
            raise IntegrationError(
                "INVALID_CONFIGURATION", "Invalid Keychain service name", 422
            )
        subprocess.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-a",
                account,
                "-s",
                service,
                "-w",
                json.dumps(value),
            ],
            check=True,
            capture_output=True,
            timeout=10,
        )
        return f"keychain://{service}"

    def store(self, tenant_id: str, connection_id: str, value: dict) -> str:
        """Persist a new credential without returning or logging its value."""
        safe_tenant = re.sub(r"[^a-zA-Z0-9_.-]", "-", tenant_id)[:80]
        secret_id = f"ai-delivery-platform/integrations/{safe_tenant}/{connection_id}"
        client = boto3.client(
            "secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-1")
        )
        payload = json.dumps(value)
        try:
            client.create_secret(
                Name=secret_id,
                Description="Axiom Delivery AI integration credential",
                SecretString=payload,
                ClientRequestToken=str(uuid4()),
                Tags=[{"Key": "application", "Value": "ai-delivery-platform"}],
            )
        except client.exceptions.ResourceExistsException:
            client.put_secret_value(
                SecretId=secret_id,
                SecretString=payload,
                ClientRequestToken=str(uuid4()),
            )
        return f"aws-secrets://{secret_id}"


secret_provider = SecretProvider()
