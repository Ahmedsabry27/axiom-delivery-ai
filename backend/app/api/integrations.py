from __future__ import annotations

import asyncio
import base64
import os
import re
import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import perf_counter
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy.orm import Session

from app.api.tools import identity
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.agent import Agent
from app.database.models.audit import AuditLog
from app.database.models.integration import (
    IntegrationAgentAssignment,
    IntegrationCapability,
    IntegrationConnection,
    IntegrationMapping,
    IntegrationOAuthState,
    IntegrationQuarantine,
    IntegrationSourceRecord,
    IntegrationSyncRun,
    IntegrationUsage,
    IntegrationWebhookSubscription,
    ProviderAuthorization,
)
from app.integrations.errors import IntegrationError
from app.integrations.provisioning import (
    disable_connection_capabilities,
    provision_capability,
    sync_connection_assignments,
    unprovision_capability,
)
from app.integrations.registry import connector_registry
from app.integrations.secrets import secret_provider
from app.integrations.simulation import PROFILES
from app.integrations.simulation import records as simulated_records
from app.tool_discovery.indexing import index_tools
from app.tool_sdk.service import registry

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])

PROVIDER_SCOPES = {
    "atlassian": [
        "read:jira-work",
        "read:jira-user",
        "read:confluence-content.all",
        "read:confluence-space.summary",
    ],
    "microsoft": [
        "User.Read",
        "Calendars.Read",
        "OnlineMeetings.Read",
        "OnlineMeetingTranscript.Read.All",
    ],
}
MICROSOFT_CALENDAR_SCOPES = [
    "openid",
    "profile",
    "offline_access",
    "User.Read",
    "Calendars.Read",
]
PROVIDER_CALLBACKS = {
    "atlassian": "/api/integrations/atlassian/callback",
    "microsoft": "/api/integrations/microsoft/callback",
}

CATALOG = [
    {
        "type": "jira",
        "name": "Jira Cloud",
        "category": "Delivery management",
        "description": "Jira delivery synchronization with schema-aware mappings and approval-controlled actions.",
        "auth_methods": ["oauth2", "api_token"],
        "read_capabilities": 5,
        "write_capabilities": 5,
        "supported_direction": ["INBOUND", "OUTBOUND"],
        "supported_entities": ["Jira projects", "Jira issues"],
        "synchronization_modes": ["FULL", "INCREMENTAL", "MANUAL"],
        "availability": "BETA",
        "maturity": "Simulator validated; live sandbox pending",
        "limitations": [
            "Live Atlassian OAuth and sandbox validation require provider credentials"
        ],
    },
    {
        "type": "azure_devops",
        "name": "Azure DevOps",
        "category": "Delivery management",
        "description": "Boards, iterations, and work items.",
        "auth_methods": ["oauth2"],
        "supported_direction": ["INBOUND"],
        "supported_entities": ["Projects", "Sprints", "Work items"],
        "synchronization_modes": [],
        "availability": "PLANNED",
        "maturity": "Definition only",
    },
    {
        "type": "servicenow",
        "name": "ServiceNow",
        "category": "IT service management",
        "description": "Service management records and workflows.",
        "auth_methods": ["oauth2", "api_token"],
        "supported_direction": ["INBOUND"],
        "supported_entities": ["Change records", "Incidents"],
        "synchronization_modes": [],
        "availability": "PLANNED",
        "maturity": "Definition only",
    },
    {
        "type": "confluence",
        "name": "Confluence",
        "category": "Knowledge and documents",
        "description": "Pages as governed evidence.",
        "auth_methods": ["oauth2"],
        "supported_direction": ["INBOUND"],
        "supported_entities": ["Evidence"],
        "synchronization_modes": ["FULL", "INCREMENTAL", "EVENT_DRIVEN", "MANUAL"],
        "availability": "BETA",
        "maturity": "Simulator validated; live sandbox pending",
    },
    {
        "type": "microsoft_teams",
        "name": "Microsoft Teams",
        "category": "Meetings and collaboration",
        "description": "Meeting and collaboration records.",
        "auth_methods": ["oauth2"],
        "supported_direction": ["INBOUND"],
        "supported_entities": ["Meetings"],
        "synchronization_modes": ["FULL", "INCREMENTAL", "EVENT_DRIVEN", "MANUAL"],
        "availability": "BETA",
        "maturity": "Simulator validated; live sandbox pending",
    },
    {
        "type": "outlook_calendar",
        "name": "Outlook Calendar",
        "category": "Meetings and collaboration",
        "description": "Calendar events as meeting inputs.",
        "auth_methods": ["oauth2"],
        "supported_direction": ["INBOUND"],
        "supported_entities": ["Meetings"],
        "synchronization_modes": ["FULL", "INCREMENTAL", "EVENT_DRIVEN", "MANUAL"],
        "availability": "BETA",
        "maturity": "Simulator validated; live sandbox pending",
    },
    {
        "type": "file_import",
        "name": "CSV / JSON Import",
        "category": "File import",
        "description": "Validated local delivery-data import.",
        "auth_methods": ["none"],
        "supported_direction": ["INBOUND"],
        "supported_entities": [],
        "synchronization_modes": [],
        "availability": "PLANNED",
        "maturity": "Definition only",
    },
    {
        "type": "mcp",
        "name": "Existing MCP servers",
        "category": "MCP",
        "description": "Operational through the existing tenant-scoped MCP administration workspace.",
        "auth_methods": ["none", "api_key", "oauth2"],
        "supported_direction": ["BIDIRECTIONAL"],
        "supported_entities": ["Tools", "Resources", "Prompts"],
        "synchronization_modes": ["MANUAL"],
        "availability": "AVAILABLE",
        "maturity": "Existing MCP framework",
        "setup_route": "/mcp-servers",
    },
    {
        "type": "github",
        "name": "GitHub",
        "category": "Developer Tools",
        "description": "Repositories, issues, pull requests and workflows.",
        "auth_methods": ["oauth2", "api_token"],
    },
    {
        "type": "microsoft_graph",
        "name": "Microsoft Graph",
        "category": "Productivity",
        "description": "Microsoft 365 resources through Graph.",
        "auth_methods": ["oauth2"],
    },
    {
        "type": "sharepoint",
        "name": "SharePoint",
        "category": "Knowledge and documents",
        "description": "Sites, libraries and enterprise content.",
        "auth_methods": ["oauth2"],
        "supported_direction": ["INBOUND"],
        "supported_entities": ["Evidence"],
        "synchronization_modes": [],
        "availability": "PLANNED",
        "maturity": "Definition only",
    },
    {
        "type": "azure_blob",
        "name": "Azure Blob",
        "category": "Cloud Storage",
        "description": "Azure object storage containers and blobs.",
        "auth_methods": ["managed_identity", "oauth2"],
    },
    {
        "type": "azure_key_vault",
        "name": "Azure Key Vault",
        "category": "Secrets",
        "description": "Governed access to Azure secrets and keys.",
        "auth_methods": ["managed_identity", "oauth2"],
    },
    {
        "type": "slack",
        "name": "Slack",
        "category": "Collaboration",
        "description": "Channels, messages and collaboration workflows.",
        "auth_methods": ["oauth2"],
    },
    {
        "type": "salesforce",
        "name": "Salesforce",
        "category": "CRM",
        "description": "CRM objects, search and business workflows.",
        "auth_methods": ["oauth2"],
    },
    {
        "type": "sap",
        "name": "SAP",
        "category": "Financial systems",
        "description": "Enterprise resource planning capabilities.",
        "auth_methods": ["oauth2", "client_credentials"],
        "supported_direction": ["INBOUND"],
        "supported_entities": [],
        "synchronization_modes": [],
        "availability": "PLANNED",
        "maturity": "Definition only",
    },
    {
        "type": "rest_api",
        "name": "Generic REST API",
        "category": "Developer/API",
        "description": "Schema-driven governed REST capabilities.",
        "auth_methods": ["api_token", "oauth2"],
        "supported_direction": ["INBOUND", "OUTBOUND"],
        "supported_entities": [],
        "synchronization_modes": [],
        "availability": "PLANNED",
        "maturity": "Definition only",
    },
]


def require(user: dict, permission: str):
    ctx = identity(user)
    if "tools.admin" not in ctx.permissions and permission not in ctx.permissions:
        raise HTTPException(
            403,
            {
                "code": "PERMISSION_DENIED",
                "message": f"{permission} permission is required",
            },
        )
    return ctx


def audit(
    db: Session,
    ctx,
    event: str,
    row: IntegrationConnection,
    metadata: dict | None = None,
):
    db.add(
        AuditLog(
            tenant_id=ctx.tenant_id,
            user_id=ctx.actor_id,
            event_type=event,
            entity="integration_connection",
            entity_id=row.id,
            timestamp=datetime.now(UTC),
            actor_id=ctx.actor_id,
            action=event,
            target_type="integration_connection",
            target_id=row.id,
            metadata_json=metadata or {},
            created_at=datetime.now(UTC),
        )
    )


def get_row(db: Session, tenant_id: str, connection_id: str) -> IntegrationConnection:
    row = (
        db.query(IntegrationConnection)
        .filter_by(id=connection_id, tenant_id=tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(
            404,
            {
                "code": "INTEGRATION_NOT_FOUND",
                "message": "Integration connection not found",
            },
        )
    return row


def counts(db: Session, row: IntegrationConnection) -> dict:
    capabilities = (
        db.query(IntegrationCapability)
        .filter_by(connection_id=row.id, tenant_id=row.tenant_id)
        .all()
    )
    return {
        "tools_count": sum(
            x.capability_type == "tool" and x.provisioned for x in capabilities
        ),
        "actions_count": sum(
            x.capability_type == "action" and x.provisioned for x in capabilities
        ),
        "agents_count": db.query(IntegrationAgentAssignment)
        .filter_by(connection_id=row.id, tenant_id=row.tenant_id)
        .count(),
    }


def serialize(db: Session, row: IntegrationConnection) -> dict:
    return {
        "id": row.id,
        "connector_type": row.connector_type,
        "name": row.name,
        "display_name": row.display_name,
        "description": row.description,
        "auth_type": row.auth_type,
        "status": row.status,
        "health_status": row.health_status,
        "base_url": row.base_url,
        "credential_configured": bool(row.secret_ref),
        "configuration": row.configuration,
        "metadata": row.safe_metadata,
        "last_verified_at": row.last_verified_at,
        "last_error_code": row.last_error_code,
        "last_error_message_safe": row.last_error_message_safe,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "enabled": row.enabled,
        "lock_version": row.lock_version,
        **counts(db, row),
    }


class ConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connector_type: str = Field(min_length=1, max_length=80)
    name: str | None = Field(None, max_length=120)
    display_name: str = Field(min_length=1, max_length=160)
    description: str = Field("", max_length=2000)
    auth_type: str
    base_url: str
    secret_ref: str | None = None
    credential_email: str | None = Field(None, max_length=320)
    credential_token: SecretStr | None = Field(None, repr=False)
    configuration: dict = Field(default_factory=dict)
    enabled: bool = False

    @field_validator("base_url")
    @classmethod
    def public_https(cls, value: str):
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.hostname in {"localhost", "127.0.0.1"}
        ):
            raise ValueError("base_url must be a public HTTPS URL")
        return value.rstrip("/")

    @field_validator("secret_ref")
    @classmethod
    def valid_secret_reference(cls, value: str | None):
        if value and not value.startswith(
            ("env://", "aws-secrets://", "simulator://", "keychain://")
        ):
            raise ValueError(
                "Use Jira email and API token fields for credentials, or provide an env:// or aws-secrets:// reference"
            )
        return value


class ConnectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(None, min_length=1, max_length=160)
    description: str | None = Field(None, max_length=2000)
    auth_type: str | None = None
    base_url: str | None = None
    secret_ref: str | None = None
    configuration: dict | None = None
    enabled: bool | None = None
    lock_version: int


class CapabilityUpdate(BaseModel):
    enabled: bool | None = None
    approval_required: bool | None = None
    governance: dict | None = None


class AssignmentPayload(BaseModel):
    capability_names: list[str] = Field(default_factory=list)


class ExecutionPayload(BaseModel):
    arguments: dict = Field(default_factory=dict)
    agent_id: str | None = None
    execution_id: str | None = None


class OAuthConnectPayload(BaseModel):
    redirect_uri: str
    simulator: bool = False

    @field_validator("redirect_uri")
    @classmethod
    def allowed_redirect(cls, value: str):
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("A valid redirect URI is required")
        if parsed.scheme == "http" and parsed.hostname not in {
            "localhost",
            "127.0.0.1",
        }:
            raise ValueError("HTTP callbacks are allowed only for local development")
        return value


class SyncPayload(BaseModel):
    mode: str = "INCREMENTAL"
    trigger: str = "MANUAL"

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, value: str):
        if value not in {"FULL", "INCREMENTAL", "EVENT_DRIVEN", "MANUAL"}:
            raise ValueError("Unsupported synchronization mode")
        return value


@router.get("/catalog")
def catalog(user: dict = Depends(get_current_user)):
    require(user, "integrations.read")
    implemented = connector_registry.implemented()
    return [
        {
            **item,
            "implementation_status": "available"
            if item.get("availability") == "AVAILABLE"
            else "beta"
            if item.get("availability") == "BETA" and item["type"] in implemented
            else "coming_soon",
            "availability": item.get("availability", "PLANNED"),
        }
        for item in CATALOG
    ]


def _provider(provider: str) -> str:
    if provider not in PROVIDER_SCOPES:
        raise HTTPException(
            404, {"code": "PROVIDER_NOT_FOUND", "message": "Provider not found"}
        )
    return provider


@router.post("/{provider}/connect")
def provider_connect(
    provider: str,
    payload: OAuthConnectPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    provider = _provider(provider)
    ctx = require(user, "integrations.manage")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    verifier_ref = None
    if not payload.simulator and provider == "microsoft":
        verifier_ref = secret_provider.store_keychain(
            f"axiom.ai-delivery-platform.oauth-state.{sha256(state.encode()).hexdigest()[:24]}",
            ctx.actor_id,
            {"code_verifier": verifier},
        )
    db.add(
        IntegrationOAuthState(
            state_hash=sha256(state.encode()).hexdigest(),
            tenant_id=ctx.tenant_id,
            actor_id=ctx.actor_id,
            provider=provider,
            redirect_uri=payload.redirect_uri,
            code_verifier_ref=(
                f"simulator://pkce/{sha256(verifier.encode()).hexdigest()}"
                if payload.simulator
                else verifier_ref
            ),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    db.commit()
    if payload.simulator:
        authorization_url = (
            f"{payload.redirect_uri}?state={state}&code=simulated-authorization-code"
        )
    elif provider == "atlassian":
        authorization_url = "https://auth.atlassian.com/authorize"
    else:
        client_id = os.getenv(
            "MICROSOFT_GRAPH_CLIENT_ID", "dbde8708-816a-46d7-a161-ad1a1a6be55d"
        )
        challenge = (
            base64.urlsafe_b64encode(sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        authorization_url = (
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"
            + urlencode(
                {
                    "client_id": client_id,
                    "response_type": "code",
                    "redirect_uri": payload.redirect_uri,
                    "response_mode": "query",
                    "scope": " ".join(MICROSOFT_CALENDAR_SCOPES),
                    "state": state,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "prompt": "select_account",
                }
            )
        )
    return {
        "provider": provider,
        "authorization_url": authorization_url,
        "state": state if payload.simulator else None,
        "scopes": MICROSOFT_CALENDAR_SCOPES
        if provider == "microsoft"
        else PROVIDER_SCOPES[provider],
        "expires_in_seconds": 600,
        "mode": "SIMULATOR" if payload.simulator else "LIVE",
    }


@router.get("/{provider}/callback")
async def provider_callback(
    provider: str,
    state: str,
    code: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    provider = _provider(provider)
    ctx = require(user, "integrations.manage")
    row = (
        db.query(IntegrationOAuthState)
        .filter_by(
            state_hash=sha256(state.encode()).hexdigest(),
            provider=provider,
            tenant_id=ctx.tenant_id,
            actor_id=ctx.actor_id,
        )
        .first()
    )
    now = datetime.now(UTC)
    if not row or row.consumed_at or row.expires_at.replace(tzinfo=UTC) < now:
        raise HTTPException(
            400,
            {
                "code": "OAUTH_STATE_INVALID",
                "message": "Authorization state is invalid or expired",
            },
        )
    row.consumed_at = now
    if error or not code:
        db.commit()
        raise HTTPException(
            400,
            {"code": "OAUTH_DENIED", "message": "Provider authorization was denied"},
        )
    if provider == "microsoft" and code != "simulated-authorization-code":
        if not row.code_verifier_ref:
            raise HTTPException(
                400,
                {"code": "OAUTH_STATE_INVALID", "message": "PKCE state is unavailable"},
            )
        verifier = secret_provider.resolve(row.code_verifier_ref).get("code_verifier")
        client_id = os.getenv(
            "MICROSOFT_GRAPH_CLIENT_ID", "dbde8708-816a-46d7-a161-ad1a1a6be55d"
        )
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as http:
            token_response = await http.post(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                data={
                    "client_id": client_id,
                    "code": code,
                    "redirect_uri": row.redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": verifier,
                    "scope": " ".join(MICROSOFT_CALENDAR_SCOPES),
                },
            )
            if token_response.status_code != 200:
                provider_error = token_response.json()
                error_name = str(provider_error.get("error") or "token_exchange_failed")
                description = str(provider_error.get("error_description") or "")
                aadsts = re.search(r"AADSTS\d+", description)
                # Microsoft's numeric code is often only a broad category. Keep the
                # provider's human-readable reason and request identifiers so an
                # administrator can diagnose registration problems without ever
                # returning the authorization code, client secret, or token payload.
                provider_reason = re.split(
                    r"\s+(?:Trace|Correlation) ID:", description, maxsplit=1
                )[0].strip()
                db.commit()
                raise HTTPException(
                    400,
                    {
                        "code": "OAUTH_TOKEN_EXCHANGE_FAILED",
                        "message": "Microsoft authorization could not be completed",
                        "provider_error": error_name[:80],
                        "provider_code": aadsts.group(0) if aadsts else None,
                        "provider_reason": provider_reason[:500] or None,
                        "trace_id": provider_error.get("trace_id"),
                        "correlation_id": provider_error.get("correlation_id"),
                    },
                )
            token = token_response.json()
            me_response = await http.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {token['access_token']}"},
            )
            if me_response.status_code != 200:
                db.commit()
                raise HTTPException(
                    400,
                    {
                        "code": "GRAPH_PROFILE_FAILED",
                        "message": "Microsoft account verification failed",
                    },
                )
        profile = me_response.json()
        account_id = str(profile.get("id"))
        token_ref = secret_provider.store_keychain(
            f"axiom.ai-delivery-platform.microsoft.tokens.{account_id}",
            account_id,
            {
                "access_token": token["access_token"],
                "refresh_token": token.get("refresh_token"),
                "scope": token.get("scope", ""),
                "expires_at": (
                    now + timedelta(seconds=int(token.get("expires_in", 3600)))
                ).isoformat(),
            },
        )
        secret_provider.revoke(row.code_verifier_ref)
        auth = (
            db.query(ProviderAuthorization)
            .filter_by(
                tenant_id=ctx.tenant_id,
                provider="microsoft",
                provider_tenant_id=account_id,
            )
            .first()
        )
        if not auth:
            auth = ProviderAuthorization(
                tenant_id=ctx.tenant_id,
                provider="microsoft",
                provider_tenant_id=account_id,
                account_label=profile.get("displayName")
                or profile.get("userPrincipalName")
                or "Microsoft account",
                created_at=now,
            )
            db.add(auth)
        auth.granted_scopes = str(token.get("scope", "")).split()
        auth.secret_ref = token_ref
        auth.status = "CONNECTED"
        auth.expires_at = now + timedelta(seconds=int(token.get("expires_in", 3600)))
        auth.last_refreshed_at = auth.last_verified_at = now
        auth.safe_metadata = {
            "mode": "LIVE",
            "email": profile.get("mail") or profile.get("userPrincipalName"),
        }
        outlook = (
            db.query(IntegrationConnection)
            .filter_by(tenant_id=ctx.tenant_id, connector_type="outlook_calendar")
            .first()
        )
        if outlook:
            outlook.secret_ref = token_ref
            outlook.auth_type = "oauth2"
            outlook.configuration = {
                **(outlook.configuration or {}),
                "simulator": False,
                "provider_tenant_id": account_id,
            }
            outlook.safe_metadata = {"mode": "LIVE", "account": auth.account_label}
            outlook.status = "CONNECTED"
            outlook.health_status = "healthy"
            outlook.enabled = True
        db.commit()
        return {
            "status": "CONNECTED",
            "provider": "microsoft",
            "account_label": auth.account_label,
            "granted_scopes": auth.granted_scopes,
            "mode": "LIVE",
            "next": "/integrations",
        }
    if code != "simulated-authorization-code":
        db.commit()
        raise HTTPException(
            501,
            {
                "code": "LIVE_OAUTH_NOT_CONFIGURED",
                "message": "Live OAuth exchange requires sandbox client configuration",
            },
        )
    provider_tenant = (
        "axiom-atlassian-demo" if provider == "atlassian" else "axiom-microsoft-demo"
    )
    auth = (
        db.query(ProviderAuthorization)
        .filter_by(
            tenant_id=ctx.tenant_id,
            provider=provider,
            provider_tenant_id=provider_tenant,
        )
        .first()
    )
    if not auth:
        auth = ProviderAuthorization(
            tenant_id=ctx.tenant_id,
            provider=provider,
            provider_tenant_id=provider_tenant,
            account_label=f"Axiom {provider.title()} Simulator",
            created_at=now,
        )
        db.add(auth)
    auth.granted_scopes = PROVIDER_SCOPES[provider]
    auth.secret_ref = f"simulator://oauth/{provider_tenant}"
    auth.status = "CONNECTED"
    auth.expires_at = now + timedelta(hours=1)
    auth.last_refreshed_at = now
    auth.last_verified_at = now
    auth.safe_metadata = {
        "mode": "SIMULATOR",
        "site_selection_required": provider == "atlassian",
    }
    db.commit()
    return {
        "status": "CONNECTED",
        "provider": provider,
        "provider_tenant_id": provider_tenant,
        "account_label": auth.account_label,
        "granted_scopes": auth.granted_scopes,
        "mode": "SIMULATOR",
    }


@router.post("/{provider}/disconnect")
def provider_disconnect(
    provider: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    provider = _provider(provider)
    ctx = require(user, "integrations.manage")
    rows = (
        db.query(ProviderAuthorization)
        .filter_by(tenant_id=ctx.tenant_id, provider=provider)
        .all()
    )
    for row in rows:
        secret_provider.revoke(row.secret_ref)
        row.secret_ref = None
        row.status = "DISCONNECTED"
    db.commit()
    return {"provider": provider, "status": "DISCONNECTED", "authorizations": len(rows)}


def _provider_test(provider: str, db: Session, user: dict):
    provider = _provider(provider)
    ctx = require(user, "integrations.test")
    rows = (
        db.query(ProviderAuthorization)
        .filter_by(tenant_id=ctx.tenant_id, provider=provider, status="CONNECTED")
        .all()
    )
    if not rows:
        raise HTTPException(
            409,
            {
                "code": "CONSENT_REQUIRED",
                "message": "No connected provider authorization",
            },
        )
    return {
        "provider": provider,
        "healthy": True,
        "authorizations": len(rows),
        "mode": rows[0].safe_metadata.get("mode", "UNKNOWN"),
    }


@router.post("/atlassian/test")
def atlassian_provider_test(
    db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    return _provider_test("atlassian", db, user)


@router.post("/microsoft/test")
def microsoft_provider_test(
    db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    return _provider_test("microsoft", db, user)


@router.get("")
def list_connections(
    search: str | None = None,
    status: str | None = None,
    connector_type: str | None = None,
    health: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.read")
    query = db.query(IntegrationConnection).filter_by(tenant_id=ctx.tenant_id)
    if search:
        query = query.filter(IntegrationConnection.display_name.ilike(f"%{search}%"))
    if status:
        query = query.filter_by(status=status)
    if connector_type:
        query = query.filter_by(connector_type=connector_type)
    if health:
        query = query.filter_by(health_status=health)
    return [
        serialize(db, row)
        for row in query.order_by(IntegrationConnection.updated_at.desc()).all()
    ]


@router.post("", status_code=201)
def create_connection(
    payload: ConnectionCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.manage")
    connector_registry.get(payload.connector_type)
    slug = payload.name or re.sub(
        r"[^a-z0-9]+", "-", payload.display_name.lower()
    ).strip("-")
    if (
        not payload.secret_ref
        and not payload.configuration.get("simulator")
        and not (payload.credential_email and payload.credential_token)
    ):
        raise HTTPException(
            422,
            {
                "code": "INVALID_CONFIGURATION",
                "message": "Provide Jira account email and API token, or a secure secret reference",
            },
        )
    row = IntegrationConnection(
        tenant_id=ctx.tenant_id,
        connector_type=payload.connector_type,
        name=slug,
        display_name=payload.display_name,
        description=payload.description,
        auth_type=payload.auth_type,
        base_url=payload.base_url,
        secret_ref=payload.secret_ref,
        configuration=payload.configuration,
        enabled=payload.enabled,
        status="CONFIGURATION_REQUIRED",
        health_status="unknown",
        created_by=ctx.actor_id,
    )
    db.add(row)
    db.flush()
    if payload.credential_email and payload.credential_token:
        try:
            row.secret_ref = secret_provider.store(
                ctx.tenant_id,
                row.id,
                {
                    "email": payload.credential_email,
                    "api_token": payload.credential_token.get_secret_value(),
                },
            )
        except Exception as exc:
            db.rollback()
            raise HTTPException(
                503,
                {
                    "code": "SECRET_STORAGE_UNAVAILABLE",
                    "message": "The credential could not be stored securely in AWS Secrets Manager",
                },
            ) from exc
    audit(db, ctx, "integration.created", row)
    db.commit()
    db.refresh(row)
    return serialize(db, row)


@router.get("/{connection_id}")
def get_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.read")
    return serialize(db, get_row(db, ctx.tenant_id, connection_id))


@router.patch("/{connection_id}")
def update_connection(
    connection_id: str,
    payload: ConnectionUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.manage")
    row = get_row(db, ctx.tenant_id, connection_id)
    if row.lock_version != payload.lock_version:
        raise HTTPException(
            409,
            {
                "code": "LOCK_VERSION_CONFLICT",
                "message": "Connection was updated by another user",
            },
        )
    for key, value in payload.model_dump(
        exclude_unset=True, exclude={"lock_version"}
    ).items():
        setattr(row, key, value)
    row.lock_version += 1
    row.status = "configured" if row.enabled else "disabled"
    audit(db, ctx, "integration.updated", row)
    db.commit()
    db.refresh(row)
    return serialize(db, row)


@router.delete("/{connection_id}")
def disable_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.manage")
    row = get_row(db, ctx.tenant_id, connection_id)
    row.enabled = False
    row.status = "disabled"
    row.health_status = "unknown"
    disable_connection_capabilities(db, row, registry)
    row.lock_version += 1
    audit(db, ctx, "integration.disconnected", row)
    db.commit()
    return serialize(db, row)


@router.post("/{connection_id}/test")
async def test_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.test")
    row = get_row(db, ctx.tenant_id, connection_id)
    connector = connector_registry.get(row.connector_type)
    try:
        result = await connector.test_connection(
            row, secret_provider.resolve(row.secret_ref)
        )
        row.health_status = "healthy"
        row.status = "connected"
        row.enabled = True
        row.last_error_code = row.last_error_message_safe = None
        row.safe_metadata = {**row.safe_metadata, **result}
        event = "integration.connected"
    except IntegrationError as exc:
        row.health_status = "unhealthy"
        row.status = "error"
        row.last_error_code = exc.code
        row.last_error_message_safe = exc.safe_message
        result = {"healthy": False, "code": exc.code, "message": exc.safe_message}
        event = "integration.tested"
    row.last_verified_at = datetime.now(UTC)
    audit(
        db,
        ctx,
        event,
        row,
        {"healthy": result.get("healthy", True), "error_code": row.last_error_code},
    )
    db.commit()
    if not result.get("healthy", True):
        raise HTTPException(502, result)
    return result


@router.post("/{connection_id}/discover")
async def discover(
    connection_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.capabilities.manage")
    row = get_row(db, ctx.tenant_id, connection_id)
    connector = connector_registry.get(row.connector_type)
    try:
        definitions, metadata = await connector.discover_capabilities(
            row, secret_provider.resolve(row.secret_ref)
        )
    except IntegrationError as exc:
        raise HTTPException(
            exc.status_code, {"code": exc.code, "message": exc.safe_message}
        ) from None
    for item in definitions:
        capability = (
            db.query(IntegrationCapability)
            .filter_by(connection_id=row.id, external_name=item.name)
            .first()
        )
        if not capability:
            capability = IntegrationCapability(
                connection_id=row.id,
                tenant_id=ctx.tenant_id,
                external_name=item.name,
                display_name=item.display_name,
                description=item.description,
                capability_type=item.capability_type,
            )
            db.add(capability)
        capability.version = item.version
        capability.input_schema = item.input_schema
        capability.output_schema = item.output_schema
        capability.risk_level = item.risk_level
        capability.approval_required = item.approval_required
        provision_capability(db, row, capability, ctx.actor_id, registry)
    row.safe_metadata = {**row.safe_metadata, **metadata}
    sync_connection_assignments(db, row, ctx.actor_id)
    audit(
        db, ctx, "integration.capabilities.discovered", row, {"count": len(definitions)}
    )
    db.commit()
    await index_tools(db, ctx.tenant_id, batch_size=500)
    return {"capabilities": len(definitions), "metadata": metadata}


@router.get("/{connection_id}/capabilities")
def capabilities(
    connection_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.read")
    get_row(db, ctx.tenant_id, connection_id)
    return [
        {
            "id": x.id,
            "name": x.external_name,
            "display_name": x.display_name,
            "description": x.description,
            "type": x.capability_type,
            "version": x.version,
            "input_schema": x.input_schema,
            "output_schema": x.output_schema,
            "risk": x.risk_level,
            "approval_required": x.approval_required,
            "governance": x.governance,
            "enabled": x.enabled,
            "provisioned": x.provisioned,
        }
        for x in db.query(IntegrationCapability)
        .filter_by(connection_id=connection_id, tenant_id=ctx.tenant_id)
        .all()
    ]


@router.patch("/{connection_id}/capabilities/{capability_name:path}")
def update_capability(
    connection_id: str,
    capability_name: str,
    payload: CapabilityUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.capabilities.manage")
    row = get_row(db, ctx.tenant_id, connection_id)
    cap = (
        db.query(IntegrationCapability)
        .filter_by(
            connection_id=row.id, tenant_id=ctx.tenant_id, external_name=capability_name
        )
        .first()
    )
    if not cap:
        raise HTTPException(
            404,
            {
                "code": "CAPABILITY_UNAVAILABLE",
                "message": "Capability has not been discovered",
            },
        )
    for key, value in payload.model_dump(
        exclude_unset=True, exclude={"enabled"}
    ).items():
        setattr(cap, key, value)
    if payload.enabled is not None:
        if payload.enabled:
            provision_capability(db, row, cap, ctx.actor_id, registry)
        else:
            unprovision_capability(db, row, cap, registry)
        audit(
            db,
            ctx,
            f"integration.capability.{'enabled' if payload.enabled else 'disabled'}",
            row,
            {"capability": cap.external_name},
        )
    db.commit()
    return {
        "name": cap.external_name,
        "enabled": cap.enabled,
        "provisioned": cap.provisioned,
    }


@router.get("/{connection_id}/agents")
def connection_agents(
    connection_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.read")
    get_row(db, ctx.tenant_id, connection_id)
    assignments = {
        x.agent_id: x
        for x in db.query(IntegrationAgentAssignment)
        .filter_by(connection_id=connection_id, tenant_id=ctx.tenant_id)
        .all()
    }
    return [
        {
            "id": a.id,
            "uuid": a.uuid,
            "name": a.name,
            "status": a.lifecycle_status,
            "assigned": a.id in assignments,
            "capability_names": assignments[a.id].capability_names
            if a.id in assignments
            else [],
        }
        for a in db.query(Agent).filter_by(tenant_id=ctx.tenant_id).all()
    ]


@router.post("/{connection_id}/agents/{agent_id}")
def assign_agent(
    connection_id: str,
    agent_id: int,
    payload: AssignmentPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.agents.manage")
    row = get_row(db, ctx.tenant_id, connection_id)
    agent = db.query(Agent).filter_by(id=agent_id, tenant_id=ctx.tenant_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    valid = {
        x.external_name: x
        for x in db.query(IntegrationCapability)
        .filter_by(
            connection_id=row.id,
            tenant_id=ctx.tenant_id,
            enabled=True,
            provisioned=True,
        )
        .all()
    }
    if not set(payload.capability_names) <= set(valid):
        raise HTTPException(
            422,
            {
                "code": "CAPABILITY_UNAVAILABLE",
                "message": "Assign only enabled, provisioned capabilities",
            },
        )
    assignment = (
        db.query(IntegrationAgentAssignment)
        .filter_by(connection_id=row.id, agent_id=agent.id)
        .first()
    )
    if not assignment:
        assignment = IntegrationAgentAssignment(
            connection_id=row.id,
            agent_id=agent.id,
            tenant_id=ctx.tenant_id,
            created_by=ctx.actor_id,
        )
        db.add(assignment)
    assignment.capability_names = payload.capability_names
    db.flush()
    sync_connection_assignments(db, row, ctx.actor_id, agent_ids={agent.id})
    audit(
        db,
        ctx,
        "integration.agent.assigned",
        row,
        {"agent_id": agent.uuid, "capabilities": payload.capability_names},
    )
    db.commit()
    return {"assigned": True}


@router.delete("/{connection_id}/agents/{agent_id}")
def unassign_agent(
    connection_id: str,
    agent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.agents.manage")
    row = get_row(db, ctx.tenant_id, connection_id)
    assignment = (
        db.query(IntegrationAgentAssignment)
        .filter_by(connection_id=row.id, agent_id=agent_id, tenant_id=ctx.tenant_id)
        .first()
    )
    if assignment:
        db.delete(assignment)
        db.flush()
        sync_connection_assignments(db, row, ctx.actor_id, agent_ids={agent_id})
    audit(db, ctx, "integration.agent.unassigned", row, {"agent_id": agent_id})
    db.commit()
    return {"assigned": False}


@router.post("/{connection_id}/execute/{capability_name:path}")
async def execute(
    connection_id: str,
    capability_name: str,
    payload: ExecutionPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.execute")
    row = get_row(db, ctx.tenant_id, connection_id)
    cap = (
        db.query(IntegrationCapability)
        .filter_by(
            connection_id=row.id,
            tenant_id=ctx.tenant_id,
            external_name=capability_name,
            enabled=True,
            provisioned=True,
        )
        .first()
    )
    if not cap:
        raise HTTPException(
            422,
            {"code": "CAPABILITY_UNAVAILABLE", "message": "Capability is not enabled"},
        )
    required = cap.input_schema.get("required", [])
    missing = [name for name in required if payload.arguments.get(name) in (None, "")]
    if missing:
        return {
            "status": "WAITING_FOR_INPUT",
            "missing_fields": missing,
            "input_schema": cap.input_schema,
            "connection_id": row.id,
            "capability": cap.external_name,
            "execution_id": payload.execution_id,
        }
    if cap.capability_type == "action" and cap.approval_required:
        return {
            "status": "WAITING_FOR_APPROVAL",
            "connection_id": row.id,
            "capability": cap.external_name,
            "execution_id": payload.execution_id,
        }
    started = perf_counter()
    connector = connector_registry.get(row.connector_type)
    try:
        secret = secret_provider.resolve(row.secret_ref)
        result = await (
            connector.execute_tool(row, cap.external_name, payload.arguments, secret)
            if cap.capability_type == "tool"
            else connector.execute_action(
                row, cap.external_name, payload.arguments, secret
            )
        )
        status = "succeeded"
        error_code = None
    except IntegrationError as exc:
        result = None
        status = "failed"
        error_code = exc.code
        db.add(
            IntegrationUsage(
                connection_id=row.id,
                tenant_id=ctx.tenant_id,
                capability_name=cap.external_name,
                capability_type=cap.capability_type,
                agent_id=payload.agent_id,
                actor_id=ctx.actor_id,
                execution_id=payload.execution_id,
                status=status,
                latency_ms=(perf_counter() - started) * 1000,
                error_code=error_code,
            )
        )
        audit(
            db,
            ctx,
            f"integration.{cap.capability_type}.executed",
            row,
            {
                "capability": cap.external_name,
                "status": status,
                "error_code": error_code,
            },
        )
        db.commit()
        raise HTTPException(
            exc.status_code, {"code": exc.code, "message": exc.safe_message}
        ) from None
    db.add(
        IntegrationUsage(
            connection_id=row.id,
            tenant_id=ctx.tenant_id,
            capability_name=cap.external_name,
            capability_type=cap.capability_type,
            agent_id=payload.agent_id,
            actor_id=ctx.actor_id,
            execution_id=payload.execution_id,
            status=status,
            latency_ms=(perf_counter() - started) * 1000,
        )
    )
    audit(
        db,
        ctx,
        f"integration.{cap.capability_type}.executed",
        row,
        {"capability": cap.external_name, "status": status},
    )
    db.commit()
    return {
        "status": "SUCCEEDED",
        "result": result,
        "connection_id": row.id,
        "capability": cap.external_name,
    }


@router.get("/{connection_id}/usage")
def usage(
    connection_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.read")
    get_row(db, ctx.tenant_id, connection_id)
    rows = (
        db.query(IntegrationUsage)
        .filter_by(connection_id=connection_id, tenant_id=ctx.tenant_id)
        .all()
    )
    succeeded = sum(x.status == "succeeded" for x in rows)
    failed = len(rows) - succeeded
    return {
        "requests": len(rows),
        "successful": succeeded,
        "failed": failed,
        "average_latency_ms": round(sum(x.latency_ms or 0 for x in rows) / len(rows), 2)
        if rows
        else 0,
        "recent": [
            {
                "capability": x.capability_name,
                "type": x.capability_type,
                "agent_id": x.agent_id,
                "status": x.status,
                "latency_ms": x.latency_ms,
                "error_code": x.error_code,
                "timestamp": x.created_at,
            }
            for x in rows[-50:][::-1]
        ],
    }


def _summary(
    connection_type: str, source_rows: list[IntegrationSourceRecord], quarantine: int
) -> dict:
    counts_by_type: dict[str, int] = {}
    for item in source_rows:
        counts_by_type[item.external_entity_type] = (
            counts_by_type.get(item.external_entity_type, 0) + 1
        )
    if connection_type == "jira":
        return {
            "projects": counts_by_type.get("project", 0),
            "boards": counts_by_type.get("board", 0),
            "sprints": counts_by_type.get("sprint", 0),
            "issues": counts_by_type.get("issue", 0),
            "mapping_health": round(
                100 - (quarantine / max(len(source_rows) + quarantine, 1) * 100), 1
            ),
            "rate_limit_state": "NORMAL",
        }
    if connection_type == "confluence":
        return {
            "spaces": counts_by_type.get("space", 0),
            "pages": counts_by_type.get("page", 0),
            "evidence_records": counts_by_type.get("page", 0),
            "stale_pages": sum(
                item.external_entity_type == "page" and item.data_status == "STALE"
                for item in source_rows
            ),
            "restricted_pages": sum(
                item.external_entity_type == "page"
                and item.classification == "RESTRICTED"
                for item in source_rows
            ),
        }
    if connection_type == "outlook_calendar":
        return {
            "calendars": counts_by_type.get("calendar", 0),
            "events": counts_by_type.get("event", 0),
            "recurring_series": counts_by_type.get("series", 0),
            "meeting_window": "90 days",
            "subscription_status": "ACTIVE",
        }
    if connection_type == "microsoft_teams":
        return {
            "meetings": counts_by_type.get("meeting", 0),
            "transcripts_available": 6,
            "transcripts_ingested": counts_by_type.get("transcript", 0),
            "meetings_without_transcript": 1,
            "extracted_review_items": counts_by_type.get("review_item", 0),
            "subscription_status": "RENEWAL_DUE",
            "permission_status": "ADMIN SETTING WARNING",
        }
    return {"records": len(source_rows), "quarantined": quarantine}


@router.post("/{connection_id}/sync")
async def synchronize(
    connection_id: str,
    payload: SyncPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.manage")
    row = get_row(db, ctx.tenant_id, connection_id)
    if row.connector_type not in PROFILES:
        raise HTTPException(
            422,
            {
                "code": "SYNC_UNAVAILABLE",
                "message": "Synchronization is unavailable for this connector",
            },
        )
    if not row.configuration.get("simulator", False):
        try:
            if row.connector_type == "jira":
                from scripts.sync_jira_delivery_portfolio import (
                    main as project_live_jira,
                )
                from scripts.sync_real_jira import main as sync_live_jira

                await sync_live_jira()
                await asyncio.to_thread(project_live_jira)
            elif row.connector_type == "confluence":
                from scripts.sync_real_confluence import main as sync_live_confluence

                await asyncio.to_thread(sync_live_confluence)
            elif row.connector_type == "outlook_calendar":
                from scripts.sync_real_outlook import main as sync_live_outlook

                await asyncio.to_thread(sync_live_outlook)
            elif row.connector_type == "microsoft_teams":
                from scripts.sync_real_outlook import main as sync_live_outlook
                from scripts.sync_real_teams import main as sync_live_teams

                await asyncio.to_thread(sync_live_outlook)
                await asyncio.to_thread(sync_live_teams)
            else:
                raise HTTPException(
                    422,
                    {
                        "code": "LIVE_SYNC_UNAVAILABLE",
                        "message": "No live synchronization adapter is configured; simulator fallback is blocked",
                    },
                )
        except SystemExit as exc:
            # Import scripts are also CLI entry points and historically used
            # SystemExit for validation failures. Letting that escape an ASGI
            # request terminates Uvicorn and leaves every frontend query stuck.
            raise HTTPException(
                422,
                {
                    "code": "LIVE_SYNC_CONFIGURATION_INVALID",
                    "message": str(exc) or "Live synchronization is not configured",
                },
            ) from None
        db.expire_all()
        completed = (
            db.query(IntegrationSyncRun)
            .filter_by(
                connection_id=row.id,
                tenant_id=ctx.tenant_id,
                status="SUCCEEDED",
            )
            .order_by(IntegrationSyncRun.started_at.desc())
            .first()
        )
        if not completed:
            raise HTTPException(
                502,
                {
                    "code": "LIVE_SYNC_FAILED",
                    "message": "Live synchronization did not complete",
                },
            )
        return {
            "id": completed.id,
            "status": completed.status,
            "cursor_end": completed.cursor_end,
            "counters": completed.counters,
            "correlation_ref": completed.correlation_ref,
            "mode": "LIVE",
        }
    if (
        db.query(IntegrationSyncRun)
        .filter_by(connection_id=row.id, tenant_id=ctx.tenant_id, status="RUNNING")
        .first()
    ):
        raise HTTPException(
            409,
            {
                "code": "SYNC_ALREADY_RUNNING",
                "message": "A synchronization is already running",
            },
        )
    now = datetime.now(UTC)
    prior = (
        db.query(IntegrationSyncRun)
        .filter_by(connection_id=row.id, tenant_id=ctx.tenant_id, status="SUCCEEDED")
        .order_by(IntegrationSyncRun.started_at.desc())
        .first()
    )
    run = IntegrationSyncRun(
        connection_id=row.id,
        tenant_id=ctx.tenant_id,
        mode=payload.mode,
        trigger=payload.trigger,
        status="RUNNING",
        configuration_version=row.lock_version,
        mapping_version=1,
        cursor_start=prior.cursor_end if prior else None,
        correlation_ref=f"sync-{secrets.token_hex(8)}",
        started_at=now,
    )
    db.add(run)
    db.flush()
    created = updated = unchanged = 0
    provider = PROFILES[row.connector_type]["provider"]
    provider_tenant = row.configuration.get(
        "provider_tenant_id", f"axiom-{provider}-demo"
    )
    defaults = {
        "jira": [("project", "Project"), ("sprint", "Sprint"), ("issue", "Work Item")],
        "confluence": [("space", "Knowledge Source"), ("page", "Evidence")],
        "outlook_calendar": [
            ("calendar", "Calendar"),
            ("event", "Meeting"),
            ("series", "Meeting Series"),
        ],
        "microsoft_teams": [
            ("meeting", "Meeting"),
            ("transcript", "Meeting Evidence"),
            ("review_item", "Review Item"),
        ],
    }[row.connector_type]
    for external, canonical in defaults:
        if (
            not db.query(IntegrationMapping)
            .filter_by(connection_id=row.id, external_entity_type=external)
            .first()
        ):
            db.add(
                IntegrationMapping(
                    connection_id=row.id,
                    tenant_id=ctx.tenant_id,
                    external_entity_type=external,
                    canonical_entity_type=canonical,
                    field_mappings={
                        "id": "external_id",
                        "title": "title",
                        "updated": "source_updated_at",
                    },
                )
            )
    for item in simulated_records(row.connector_type):
        existing = (
            db.query(IntegrationSourceRecord)
            .filter_by(
                tenant_id=ctx.tenant_id,
                provider_tenant_id=provider_tenant,
                external_entity_type=item["external_entity_type"],
                external_entity_id=item["external_entity_id"],
            )
            .first()
        )
        if not existing:
            existing = IntegrationSourceRecord(
                connection_id=row.id,
                tenant_id=ctx.tenant_id,
                provider=provider,
                provider_tenant_id=provider_tenant,
                first_synchronized_at=now,
                **item,
            )
            db.add(existing)
            created += 1
        elif existing.content_fingerprint != item["content_fingerprint"]:
            for key, value in item.items():
                setattr(existing, key, value)
            updated += 1
        else:
            unchanged += 1
        existing.last_synchronized_at = now
        existing.last_successful_run_id = run.id
    quarantine_count = PROFILES[row.connector_type]["quarantine"]
    if (
        quarantine_count
        and not db.query(IntegrationQuarantine)
        .filter_by(connection_id=row.id, tenant_id=ctx.tenant_id)
        .first()
    ):
        db.add(
            IntegrationQuarantine(
                connection_id=row.id,
                tenant_id=ctx.tenant_id,
                external_entity_type="custom_record",
                external_entity_id=f"{row.connector_type}-invalid-001",
                rule_code="MAPPING_REQUIRED",
                safe_reason="Record requires an explicit custom-field or transcript-permission mapping",
            )
        )
    if (
        row.connector_type in {"outlook_calendar", "microsoft_teams"}
        and not db.query(IntegrationWebhookSubscription)
        .filter_by(connection_id=row.id)
        .first()
    ):
        db.add(
            IntegrationWebhookSubscription(
                connection_id=row.id,
                tenant_id=ctx.tenant_id,
                provider_subscription_id=f"sim-{row.id}",
                resource="calendar/events"
                if row.connector_type == "outlook_calendar"
                else "communications/onlineMeetings/transcripts",
                status="ACTIVE"
                if row.connector_type == "outlook_calendar"
                else "RENEWAL_DUE",
                expires_at=now + timedelta(days=2),
                last_renewed_at=now,
                safe_metadata={"mode": "SIMULATOR"},
            )
        )
    run.status = "SUCCEEDED"
    run.ended_at = now
    run.cursor_end = f"sim:{now.isoformat()}"
    run.counters = {
        "discovered": created + updated + unchanged,
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "skipped": 0,
        "quarantined": quarantine_count,
        "failed": 0,
    }
    row.configuration = {
        **row.configuration,
        "simulator": True,
        "sync_cursor": run.cursor_end,
        "sync_policy": {"mode": payload.mode, "bounded_batch_size": 100},
    }
    row.safe_metadata = {
        **row.safe_metadata,
        "mode": "SIMULATOR",
        "last_sync_run_id": run.id,
    }
    row.status = "DEGRADED" if row.connector_type == "microsoft_teams" else "ACTIVE"
    row.health_status = (
        "degraded" if row.connector_type == "microsoft_teams" else "healthy"
    )
    row.enabled = True
    audit(
        db,
        ctx,
        "integration.sync.completed",
        row,
        {
            "run_id": run.id,
            "correlation_ref": run.correlation_ref,
            "counters": run.counters,
        },
    )
    db.commit()
    return {
        "id": run.id,
        "status": run.status,
        "cursor_end": run.cursor_end,
        "counters": run.counters,
        "correlation_ref": run.correlation_ref,
    }


@router.get("/{connection_id}/operations/{section}")
def integration_operations(
    connection_id: str,
    section: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require(user, "integrations.read")
    row = get_row(db, ctx.tenant_id, connection_id)
    source_query = db.query(IntegrationSourceRecord).filter_by(
        connection_id=row.id, tenant_id=ctx.tenant_id
    )
    provider_tenant_id = (row.configuration or {}).get("provider_tenant_id")
    if not (row.configuration or {}).get("simulator", False) and provider_tenant_id:
        source_query = source_query.filter_by(provider_tenant_id=provider_tenant_id)
    source = source_query.order_by(
        IntegrationSourceRecord.external_entity_type,
        IntegrationSourceRecord.external_entity_id,
    ).all()
    quarantined = (
        db.query(IntegrationQuarantine)
        .filter_by(connection_id=row.id, tenant_id=ctx.tenant_id)
        .all()
    )
    if section == "overview":
        summary = _summary(row.connector_type, source, len(quarantined))
        if (
            row.connector_type == "outlook_calendar"
            and row.safe_metadata.get("mode") == "LIVE"
        ):
            summary.update(
                {
                    "account": row.safe_metadata.get("account", "Microsoft account"),
                    "meeting_window": "30 days past / 90 days future",
                    "subscription_status": "MANUAL SYNCHRONIZATION",
                    "provider": "Microsoft Graph",
                }
            )
        if (
            row.connector_type == "microsoft_teams"
            and row.safe_metadata.get("mode") == "LIVE"
        ):
            summary = {
                "meetings": sum(
                    item.external_entity_type == "meeting" for item in source
                ),
                "transcripts_available": 0,
                "transcripts_ingested": 0,
                "meetings_without_transcript": sum(
                    item.external_entity_type == "meeting" for item in source
                ),
                "extracted_review_items": 0,
                "account": row.safe_metadata.get("account", "Microsoft account"),
                "provider": "Microsoft Graph calendar events",
                "subscription_status": "MANUAL SYNCHRONIZATION",
                "permission_status": "PERSONAL ACCOUNT — TRANSCRIPTS AND ATTENDANCE UNSUPPORTED",
            }
        return {
            "summary": summary,
            "mode": row.safe_metadata.get("mode", "NOT_CONFIGURED"),
            "status": row.status,
            "last_sync": row.configuration.get("sync_cursor"),
        }
    if section == "configuration":
        return {
            "source_scope": row.configuration.get(
                "source_scope", {"selection": "All authorized demo sources"}
            ),
            "sync_policy": row.configuration.get(
                "sync_policy", {"mode": "INCREMENTAL", "bounded_batch_size": 100}
            ),
            "connector": row.connector_type,
            "simulated": row.configuration.get("simulator", False),
        }
    if section == "authentication":
        authorization = None
        provider = PROFILES.get(row.connector_type, {}).get("provider", "atlassian")
        if provider_tenant_id:
            authorization = (
                db.query(ProviderAuthorization)
                .filter_by(
                    tenant_id=ctx.tenant_id,
                    provider=provider,
                    provider_tenant_id=provider_tenant_id,
                )
                .first()
            )
        return {
            "auth_type": row.auth_type,
            "credential_configured": bool(row.secret_ref),
            "secret_value_returned": False,
            "account": authorization.account_label if authorization else None,
            "granted_scopes": authorization.granted_scopes
            if authorization
            else PROVIDER_SCOPES[provider],
            "status": authorization.status if authorization else row.status,
            "last_verified_at": authorization.last_verified_at
            if authorization
            else None,
            "token_expires_at": authorization.expires_at if authorization else None,
            "missing_scopes": [],
        }
    if section == "mappings":
        return [
            {
                "id": x.id,
                "external_entity_type": x.external_entity_type,
                "canonical_entity_type": x.canonical_entity_type,
                "mapping_version": x.mapping_version,
                "field_mappings": x.field_mappings,
                "authority_policy": x.authority_policy,
                "enabled": x.enabled,
            }
            for x in db.query(IntegrationMapping)
            .filter_by(connection_id=row.id, tenant_id=ctx.tenant_id)
            .all()
        ]
    if section == "synchronization":
        return {
            "supported_modes": ["FULL", "INCREMENTAL", "MANUAL"]
            + (
                ["EVENT_DRIVEN"]
                if row.connector_type in {"outlook_calendar", "microsoft_teams"}
                else []
            ),
            "cursor": row.configuration.get("sync_cursor"),
            "policy": row.configuration.get("sync_policy"),
            "overlap_prevention": True,
            "cursor_commit": "after batch commit",
        }
    if section == "runs":
        return [
            {
                "id": x.id,
                "mode": x.mode,
                "trigger": x.trigger,
                "status": x.status,
                "cursor_start": x.cursor_start,
                "cursor_end": x.cursor_end,
                "counters": x.counters,
                "correlation_ref": x.correlation_ref,
                "started_at": x.started_at,
                "ended_at": x.ended_at,
            }
            for x in db.query(IntegrationSyncRun)
            .filter_by(connection_id=row.id, tenant_id=ctx.tenant_id)
            .order_by(IntegrationSyncRun.started_at.desc())
            .limit(25)
        ]
    if section == "data-quality":
        return {
            "score": round(
                100 - (len(quarantined) / max(len(source) + len(quarantined), 1) * 100),
                1,
            ),
            "valid_records": len(source),
            "quarantined": len(quarantined),
            "rules_version": "2026.08",
            "quarantine": [
                {
                    "id": x.id,
                    "entity_type": x.external_entity_type,
                    "external_id": x.external_entity_id,
                    "rule": x.rule_code,
                    "reason": x.safe_reason,
                    "status": x.status,
                }
                for x in quarantined
            ],
        }
    if section == "source-records":
        return [
            {
                "id": x.id,
                "entity_type": x.external_entity_type,
                "external_id": x.external_entity_id,
                "canonical_type": x.canonical_entity_type,
                "canonical_id": x.canonical_entity_id,
                "title": x.title,
                "version": x.source_version,
                "fingerprint": x.content_fingerprint,
                "status": x.data_status,
                "classification": x.classification,
                "source_url": x.source_url,
                "last_synchronized_at": x.last_synchronized_at,
            }
            for x in source[:100]
        ]
    if section == "webhooks":
        if (
            row.connector_type in {"outlook_calendar", "microsoft_teams"}
            and row.safe_metadata.get("mode") == "LIVE"
        ):
            return []
        return [
            {
                "id": x.id,
                "resource": x.resource,
                "status": x.status,
                "expires_at": x.expires_at,
                "last_renewed_at": x.last_renewed_at,
                "metadata": x.safe_metadata,
            }
            for x in db.query(IntegrationWebhookSubscription)
            .filter_by(connection_id=row.id, tenant_id=ctx.tenant_id)
            .all()
        ]
    if section == "access":
        return {
            "tenant_scope": ctx.tenant_id,
            "read_permission": "integrations.read",
            "manage_permission": "integrations.manage",
            "outbound": "Approval required",
            "secret_boundary": "Opaque reference only",
        }
    if section == "activity":
        return [
            {
                "event": x.event_type,
                "actor": x.actor_id,
                "timestamp": x.timestamp,
                "metadata": x.metadata_json,
            }
            for x in db.query(AuditLog)
            .filter_by(tenant_id=ctx.tenant_id, entity_id=row.id)
            .order_by(AuditLog.timestamp.desc())
            .limit(50)
        ]
    raise HTTPException(
        404, {"code": "SECTION_NOT_FOUND", "message": "Integration section not found"}
    )
