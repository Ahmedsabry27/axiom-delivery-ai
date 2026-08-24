from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.audit import AuditLog
from app.database.models.setting import SettingValue, SettingVersion
from app.settings.catalog import CATALOG, DEFINITIONS, public_definition, validate_value

router = APIRouter(prefix="/api/settings", tags=["Enterprise Settings"])
Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]
PERSONAL = {"profile", "preferences", "appearance", "notifications", "ai"}
WORKSPACE = {"workspace", "delivery", "reporting", "features"}


class Patch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: dict[str, Any]
    expected_versions: dict[str, int] = Field(default_factory=dict)
    effective_from: datetime | None = None
    reason: str = Field(default="", max_length=500)


def identity(user: dict) -> tuple[str, str]:
    return str(user.get("custom:tenant_id") or user.get("tenant_id") or "default"), str(
        user.get("sub") or "unknown"
    )


def admin(user: dict) -> bool:
    groups = user.get("cognito:groups") or user.get("groups") or []
    if isinstance(groups, str):
        groups = groups.split(",")
    return bool({"platform-admin", "workspace-admin", "governance-admin"} & set(groups))


def resolve(db: Session, user: dict, category: str | None = None) -> list[dict]:
    tenant, actor = identity(user)
    rows = db.scalars(
        select(SettingValue).where(SettingValue.tenant_id == tenant)
    ).all()
    indexed = {(row.scope, row.user_id, row.key): row for row in rows}
    result = []
    for definition in DEFINITIONS:
        if category and definition.category != category:
            continue
        tenant_row = indexed.get(("tenant", "", definition.key))
        user_row = indexed.get(("user", actor, definition.key))
        selected = user_row or tenant_row
        result.append(
            public_definition(definition)
            | {
                "effective_value": selected.value if selected else definition.default,
                "source_scope": selected.scope if selected else "platform",
                "inherited": selected is None
                or (selected.scope == "tenant" and "user" in definition.scopes),
                "locked": definition.locked or not definition.scopes,
                "version": selected.version if selected else 0,
                "last_updated": selected.updated_at if selected else None,
            }
        )
    return result


def write_category(category: str, payload: Patch, db: Session, user: dict) -> dict:
    tenant, actor = identity(user)
    scope = "user" if category in PERSONAL else "tenant"
    if category in WORKSPACE and not admin(user):
        raise HTTPException(
            403,
            {
                "code": "PERMISSION_DENIED",
                "message": "Workspace administrator permission is required",
            },
        )
    if category not in PERSONAL | WORKSPACE:
        raise HTTPException(405, "This category is read-only")
    correlation = str(uuid4())
    now = datetime.now(UTC)
    for key, raw in payload.values.items():
        definition = CATALOG.get(key)
        if not definition or definition.category != category:
            raise HTTPException(
                422,
                {
                    "code": "UNKNOWN_SETTING",
                    "field": key,
                    "correlation_id": correlation,
                },
            )
        if scope not in definition.scopes:
            raise HTTPException(
                403,
                {"code": "SETTING_LOCKED", "field": key, "correlation_id": correlation},
            )
        try:
            value = validate_value(definition, raw)
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(
                422,
                {
                    "code": "INVALID_SETTING",
                    "field": key,
                    "message": str(exc),
                    "correlation_id": correlation,
                },
            ) from exc
        query = select(SettingValue).where(
            SettingValue.tenant_id == tenant,
            SettingValue.scope == scope,
            SettingValue.key == key,
            SettingValue.user_id == (actor if scope == "user" else ""),
        )
        row = db.scalar(query)
        expected = payload.expected_versions.get(key, 0)
        if (row.version if row else 0) != expected:
            raise HTTPException(
                409,
                {
                    "code": "STALE_SETTING_VERSION",
                    "field": key,
                    "correlation_id": correlation,
                },
            )
        previous = row.value if row else definition.default
        if row is None:
            row = SettingValue(
                tenant_id=tenant,
                user_id=actor if scope == "user" else "",
                scope=scope,
                key=key,
                value=value,
                version=1,
                updated_by=actor,
                updated_at=now,
            )
            db.add(row)
            db.flush()
        else:
            row.value, row.version, row.updated_by, row.updated_at = (
                value,
                row.version + 1,
                actor,
                now,
            )
        row.effective_from = (
            payload.effective_from if definition.effective_dated else None
        )
        db.add(
            SettingVersion(
                setting_id=row.id,
                tenant_id=tenant,
                user_id=row.user_id,
                scope=scope,
                key=key,
                value=value,
                version=row.version,
                effective_from=row.effective_from,
                reason=payload.reason or None,
                changed_by=actor,
                changed_at=now,
            )
        )
        db.add(
            AuditLog(
                tenant_id=tenant,
                user_id=actor,
                event_type="SETTING_CHANGED",
                entity="setting",
                entity_id=key,
                timestamp=now,
                actor_id=actor,
                action="UPDATE",
                target_type="setting",
                target_id=key,
                correlation_id=correlation,
                before_summary={"value": previous},
                after_summary={"value": value},
                metadata_json={"scope": scope, "category": category},
                created_at=now,
                result="SUCCEEDED",
            )
        )
    db.commit()
    return {"items": resolve(db, user, category), "correlation_id": correlation}


@router.get("/schema")
def schema(user: CurrentUser):
    return {"items": [public_definition(item) for item in DEFINITIONS]}


@router.get("/effective")
def effective(db: Database, user: CurrentUser):
    return {
        "items": resolve(db, user),
        "precedence": ["platform", "tenant", "module", "user"],
    }


def category_get(category: str, db: Session, user: dict) -> dict:
    tenant, actor = identity(user)
    if category in WORKSPACE and not admin(user):
        raise HTTPException(403, "Workspace administrator permission is required")
    return {
        "category": category,
        "items": resolve(db, user, category),
        "identity": {
            "tenant_id": tenant,
            "user_id": actor,
            "name": user.get("name"),
            "email": user.get("email"),
            "roles": user.get("cognito:groups") or [],
        },
        "editable": category in PERSONAL or admin(user),
    }


for _category in (
    "profile",
    "preferences",
    "appearance",
    "notifications",
    "workspace",
    "delivery",
    "reporting",
    "ai",
    "data",
    "features",
):

    def make_get(category):
        @router.get(f"/{category}", name=f"get_settings_{category}")
        def getter(db: Database, user: CurrentUser):
            return category_get(category, db, user)

        return getter

    make_get(_category)


for _category in (
    "profile",
    "preferences",
    "appearance",
    "notifications",
    "workspace",
    "delivery",
    "reporting",
    "features",
):

    def make_patch(category):
        @router.patch(f"/{category}", name=f"patch_settings_{category}")
        def patcher(payload: Patch, db: Database, user: CurrentUser):
            return write_category(category, payload, db, user)

        return patcher

    make_patch(_category)


@router.patch("/ai/preferences")
def patch_ai(payload: Patch, db: Database, user: CurrentUser):
    return write_category("ai", payload, db, user)


@router.post("/preferences/reset")
def reset_preferences(db: Database, user: CurrentUser):
    tenant, actor = identity(user)
    rows = db.scalars(
        select(SettingValue).where(
            SettingValue.tenant_id == tenant,
            SettingValue.user_id == actor,
            SettingValue.key.like("preferences.%"),
        )
    ).all()
    for row in rows:
        db.delete(row)
    db.commit()
    return {"items": resolve(db, user, "preferences")}


@router.post("/notifications/test")
def test_notification(user: CurrentUser):
    return {
        "status": "DELIVERED_IN_APP",
        "message": "Test notification recorded for the current session",
    }


@router.post("/data/retention-preview")
def retention_preview(user: CurrentUser):
    if not admin(user):
        raise HTTPException(403, "Workspace administrator permission is required")
    return {
        "status": "PREVIEW_ONLY",
        "records_eligible": None,
        "message": "No destructive retention action was executed",
    }


@router.get("/activity")
def activity(db: Database, user: CurrentUser, limit: int = Query(50, ge=1, le=100)):
    tenant, actor = identity(user)
    query = select(SettingVersion).where(SettingVersion.tenant_id == tenant)
    if not admin(user):
        query = query.where(SettingVersion.user_id == actor)
    rows = db.scalars(
        query.order_by(SettingVersion.changed_at.desc()).limit(limit)
    ).all()
    return {
        "items": [
            {
                "setting": row.key,
                "scope": row.scope,
                "actor": row.changed_by,
                "timestamp": row.changed_at,
                "effective_date": row.effective_from,
                "version": row.version,
                "value": "REDACTED" if "secret" in row.key else row.value,
                "reason": row.reason,
            }
            for row in rows
        ]
    }
