from __future__ import annotations

import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from app.agents.models.agent import AgentDefinition, AgentStatus
from app.agents.models.capability import AgentCapability
from app.agents.models.configuration import AgentConfiguration
from app.agents.models.metadata import AgentMetadata
from app.database.models.agent import Agent, AgentActivityEvent, AgentVersion
from app.database.models.agent_assignment import (
    AgentAccessAssignment,
    AgentExecutionSetting,
    AgentKnowledgeAssignment,
    AgentToolAssignment,
)
from app.database.models.knowledge_source import KnowledgeSource
from app.database.models.tool import ToolDefinition
from app.database.models.workflow import Workflow
from app.models.runtime_execution import RuntimeExecution

ADMIN_GROUPS = {"admin", "administrators", "platform-admin"}
LIFECYCLE_TRANSITIONS = {
    "publish": {"draft", "published", "disabled"},
    "enable": {"published", "disabled"},
    "disable": {"enabled"},
    "archive": {"draft", "published", "disabled"},
    "restore": {"archived"},
}


@dataclass(frozen=True)
class AgentIdentity:
    actor_id: str
    tenant_id: str
    permissions: frozenset[str]
    groups: frozenset[str]
    roles: frozenset[str] = frozenset()
    subject_type: str = "user"

    @classmethod
    def from_claims(cls, claims: dict[str, Any]) -> AgentIdentity:
        groups = frozenset(
            str(item).lower() for item in claims.get("cognito:groups", []) or []
        )
        permissions = set(str(claims.get("scope", "")).split())
        permissions.update(str(item) for item in claims.get("permissions", []) or [])
        if groups & ADMIN_GROUPS:
            permissions.add("agents.admin")
        return cls(
            actor_id=str(claims.get("sub", "unknown")),
            tenant_id=str(claims.get("custom:tenant_id", "default")),
            permissions=frozenset(permissions),
            groups=groups,
            roles=frozenset(
                str(item).lower() for item in claims.get("roles", []) or []
            ),
            subject_type=(
                "service" if claims.get("identity_type") == "service" else "user"
            ),
        )

    def allows(self, permission: str) -> bool:
        return "agents.admin" in self.permissions or permission in self.permissions


class AgentApplicationService:
    """Tenant boundary and source of truth for managed agents."""

    def __init__(self, cache_size: int = 256) -> None:
        self._cache_size = cache_size
        self._runtime_cache: OrderedDict[tuple[str, str, int], AgentDefinition] = (
            OrderedDict()
        )

    @staticmethod
    def slugify(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        if not slug:
            raise HTTPException(
                422, {"code": "INVALID_SLUG", "message": "A stable slug is required"}
            )
        return slug[:120]

    @staticmethod
    def _require(identity: AgentIdentity, permission: str) -> None:
        if not identity.allows(permission):
            raise HTTPException(
                403,
                {
                    "code": "PERMISSION_DENIED",
                    "message": f"{permission} permission is required",
                },
            )

    def _visible(self, db: Session, identity: AgentIdentity, public_id: str) -> Agent:
        row = (
            db.query(Agent)
            .filter(
                Agent.uuid == public_id,
                Agent.tenant_id == identity.tenant_id,
                Agent.deleted_at.is_(None),
            )
            .first()
        )
        if row is None:
            raise HTTPException(
                404, {"code": "AGENT_NOT_FOUND", "message": "Agent not found"}
            )
        return row

    def _can_edit(self, row: Agent, identity: AgentIdentity) -> None:
        if row.owner_id != identity.actor_id and not identity.allows("agents.update"):
            raise HTTPException(
                403,
                {
                    "code": "PERMISSION_DENIED",
                    "message": "Agent update permission is required",
                },
            )

    @staticmethod
    def _access_subjects(identity: AgentIdentity) -> set[tuple[str, str]]:
        subjects = {(identity.subject_type, identity.actor_id)}
        subjects.update(("group", item) for item in identity.groups)
        subjects.update(("role", item) for item in identity.roles)
        return subjects

    def _has_object_access(
        self, db: Session, row: Agent, identity: AgentIdentity, action: str
    ) -> bool:
        assignment_action = {"read": "view", "update": "edit"}.get(action, action)
        subjects = self._access_subjects(identity)
        assignments = (
            db.query(AgentAccessAssignment)
            .filter_by(
                agent_id=row.id,
                tenant_id=row.tenant_id,
                action=assignment_action,
            )
            .all()
        )
        matching = [
            item
            for item in assignments
            if (item.subject_type, item.subject_id) in subjects
        ]
        if any(not item.enabled for item in matching):
            return False
        return (
            row.owner_id == identity.actor_id
            or identity.allows(f"agents.{action}")
            or any(item.enabled for item in matching)
        )

    def effective_access(
        self,
        db: Session,
        identity: AgentIdentity,
        public_id: str,
        action: str,
    ) -> dict[str, Any]:
        row = self._visible(db, identity, public_id)
        assignment_action = {"read": "view", "update": "edit"}.get(action, action)
        subjects = self._access_subjects(identity)
        matching = [
            item
            for item in db.query(AgentAccessAssignment)
            .filter_by(
                agent_id=row.id,
                tenant_id=row.tenant_id,
                action=assignment_action,
            )
            .all()
            if (item.subject_type, item.subject_id) in subjects
        ]
        explicit_denies = [item for item in matching if not item.enabled]
        direct_grants = [item for item in matching if item.enabled]
        ownership = row.owner_id == identity.actor_id
        platform_permission = identity.allows(f"agents.{action}")
        allowed = not explicit_denies and (
            ownership or platform_permission or bool(direct_grants)
        )
        if explicit_denies:
            reason = "EXPLICIT_DENY"
        elif ownership:
            reason = "OWNER"
        elif platform_permission:
            reason = "PLATFORM_PERMISSION"
        elif direct_grants:
            reason = f"{direct_grants[0].subject_type.upper()}_GRANT"
        else:
            reason = "NO_MATCHING_GRANT"
        return {
            "agent_id": row.uuid,
            "action": assignment_action,
            "subject": {
                "type": identity.subject_type,
                "id": identity.actor_id,
                "groups": sorted(identity.groups),
                "roles": sorted(identity.roles),
            },
            "ownership": ownership,
            "platform_permission": platform_permission,
            "direct_user_grants": [
                item.id for item in direct_grants if item.subject_type == "user"
            ],
            "group_grants": [
                item.id for item in direct_grants if item.subject_type == "group"
            ],
            "role_grants": [
                item.id for item in direct_grants if item.subject_type == "role"
            ],
            "explicit_denies": [item.id for item in explicit_denies],
            "approval_required": False,
            "decision": "allow" if allowed else "deny",
            "reason_codes": [reason],
        }

    def _require_object_access(
        self, db: Session, row: Agent, identity: AgentIdentity, action: str
    ) -> None:
        if not self._has_object_access(db, row, identity, action):
            raise HTTPException(
                403,
                {
                    "code": "PERMISSION_DENIED",
                    "message": f"Agent {action} permission is required",
                },
            )

    @staticmethod
    def _snapshot(data: dict[str, Any]) -> dict[str, Any]:
        return {
            "instructions": data.get("instructions", ""),
            "model_configuration": data.get("model_configuration", {}),
            "planner_configuration": data.get("planner_configuration", {}),
            "memory_configuration": data.get("memory_configuration", {}),
            "execution_limits": data.get("execution_limits", {}),
            "tool_discovery_configuration": data.get(
                "tool_discovery_configuration", {"mode": "assigned_only"}
            ),
            "capabilities": data.get("capabilities", []),
        }

    def _version(
        self, row: Agent, identity: AgentIdentity, snapshot: dict[str, Any], note: str
    ) -> AgentVersion:
        return AgentVersion(
            agent_id=row.id,
            tenant_id=row.tenant_id,
            version=row.current_version,
            instructions=snapshot["instructions"],
            model_configuration=snapshot["model_configuration"],
            planner_configuration=snapshot["planner_configuration"],
            memory_configuration=snapshot["memory_configuration"],
            execution_limits=snapshot["execution_limits"],
            tool_discovery_configuration=snapshot["tool_discovery_configuration"],
            configuration_snapshot=snapshot,
            change_note=note,
            created_by=identity.actor_id,
        )

    @staticmethod
    def _event(
        row: Agent, actor: str, event_type: str, summary: dict[str, Any]
    ) -> AgentActivityEvent:
        return AgentActivityEvent(
            agent_id=row.id,
            tenant_id=row.tenant_id,
            event_type=event_type,
            actor_id=actor,
            agent_version=row.current_version,
            summary=summary,
        )

    def create(
        self, db: Session, identity: AgentIdentity, data: dict[str, Any]
    ) -> Agent:
        self._require(identity, "agents.create")
        slug = self.slugify(data.get("slug") or data["name"])
        if (
            db.query(Agent.id)
            .filter_by(tenant_id=identity.tenant_id, slug=slug)
            .first()
        ):
            raise HTTPException(
                409,
                {"code": "AGENT_SLUG_CONFLICT", "message": "Agent slug already exists"},
            )
        snapshot = self._snapshot(data)
        now = datetime.now(UTC)
        row = Agent(
            tenant_id=identity.tenant_id,
            slug=slug,
            name=data["name"],
            description=data.get("description", ""),
            owner_id=data.get("owner_id") or identity.actor_id,
            lifecycle_status="draft",
            operational_health="unknown",
            model_configuration_ref=data.get("model_configuration_ref"),
            planner_configuration=snapshot["planner_configuration"],
            memory_configuration=snapshot["memory_configuration"],
            max_execution_steps=snapshot["execution_limits"].get("max_steps", 20),
            execution_timeout_seconds=snapshot["execution_limits"].get(
                "timeout_seconds", 120
            ),
            cost_limit=snapshot["execution_limits"].get("cost_limit"),
            risk_limit=snapshot["execution_limits"].get("risk_limit", "read"),
            environment_restrictions=snapshot["execution_limits"].get(
                "environments", []
            ),
            configuration=json.dumps(snapshot),
            created_by=identity.actor_id,
            updated_by=identity.actor_id,
            created_at=now,
            updated_at=now,
            status="DRAFT",
            health="UNKNOWN",
        )
        db.add(row)
        db.flush()
        db.add(
            AgentExecutionSetting(
                agent_id=row.id,
                tenant_id=row.tenant_id,
                max_steps=row.max_execution_steps,
                timeout_seconds=row.execution_timeout_seconds,
                cost_limit=row.cost_limit,
                risk_limit=row.risk_limit,
                updated_by=identity.actor_id,
            )
        )
        db.add(
            self._version(
                row, identity, snapshot, data.get("change_note", "Initial draft")
            )
        )
        db.add(self._event(row, identity.actor_id, "agent.created", {"slug": slug}))
        db.commit()
        db.refresh(row)
        return row

    def list_agents(
        self,
        db: Session,
        identity: AgentIdentity,
        *,
        search: str | None,
        status: str | None,
        owner: str | None,
        page: int,
        page_size: int,
        include_archived: bool,
        model: str | None = None,
        environment: str | None = None,
        sort: str = "updated_at",
        direction: str = "desc",
    ) -> tuple[list[Agent], int]:
        self._require(identity, "agents.list")
        query = db.query(Agent).filter(
            Agent.tenant_id == identity.tenant_id, Agent.deleted_at.is_(None)
        )
        if not include_archived:
            query = query.filter(Agent.lifecycle_status != "archived")
        if not identity.allows("agents.read"):
            subjects = self._access_subjects(identity)
            assigned_ids = [
                item.agent_id
                for item in db.query(AgentAccessAssignment)
                .filter_by(tenant_id=identity.tenant_id, action="view", enabled=True)
                .all()
                if (item.subject_type, item.subject_id) in subjects
            ]
            query = query.filter(
                or_(Agent.owner_id == identity.actor_id, Agent.id.in_(assigned_ids))
            )
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Agent.name.ilike(term),
                    Agent.slug.ilike(term),
                    Agent.description.ilike(term),
                )
            )
        if status:
            query = query.filter(Agent.lifecycle_status == status)
        if owner:
            query = query.filter(Agent.owner_id == owner)
        if model:
            query = query.filter(cast(Agent.configuration, String).ilike(f"%{model}%"))
        if environment:
            query = query.filter(
                cast(Agent.environment_restrictions, String).ilike(f"%{environment}%")
            )
        total = query.count()
        sort_column = {
            "name": Agent.name,
            "updated_at": Agent.updated_at,
            "lifecycle": Agent.lifecycle_status,
            "owner": Agent.owner_id,
        }.get(sort, Agent.updated_at)
        ordering = sort_column.asc() if direction == "asc" else sort_column.desc()
        return query.order_by(ordering, Agent.uuid).offset(
            (page - 1) * page_size
        ).limit(page_size).all(), total

    def get(self, db: Session, identity: AgentIdentity, public_id: str) -> Agent:
        row = self._visible(db, identity, public_id)
        self._require_object_access(db, row, identity, "read")
        return row

    def update(
        self,
        db: Session,
        identity: AgentIdentity,
        public_id: str,
        data: dict[str, Any],
        expected_version: int,
    ) -> Agent:
        row = self._visible(db, identity, public_id)
        self._require_object_access(db, row, identity, "update")
        if row.lock_version != expected_version:
            raise HTTPException(
                409,
                {
                    "code": "VERSION_CONFLICT",
                    "message": "Agent was modified by another actor",
                },
            )
        if row.lifecycle_status == "archived":
            raise HTTPException(
                409,
                {
                    "code": "AGENT_ARCHIVED",
                    "message": "Archived agents cannot be edited",
                },
            )
        prior = json.loads(row.configuration or "{}")
        snapshot = self._snapshot({**prior, **data})
        for field in ("name", "description", "model_configuration_ref"):
            if field in data:
                setattr(row, field, data[field])
        if "slug" in data:
            candidate = self.slugify(data["slug"])
            conflict = (
                db.query(Agent.id)
                .filter(
                    Agent.tenant_id == row.tenant_id,
                    Agent.slug == candidate,
                    Agent.id != row.id,
                )
                .first()
            )
            if conflict:
                raise HTTPException(
                    409,
                    {
                        "code": "AGENT_SLUG_CONFLICT",
                        "message": "Agent slug already exists",
                    },
                )
            row.slug = candidate
        row.current_version += 1
        row.instruction_version = row.current_version
        row.lock_version += 1
        row.configuration = json.dumps(snapshot)
        row.planner_configuration = snapshot["planner_configuration"]
        row.memory_configuration = snapshot["memory_configuration"]
        row.updated_by = identity.actor_id
        row.updated_at = datetime.now(UTC)
        db.add(
            self._version(
                row, identity, snapshot, data.get("change_note", "Draft updated")
            )
        )
        db.add(
            self._event(
                row,
                identity.actor_id,
                "agent.updated",
                {"changed_fields": sorted(data)},
            )
        )
        db.commit()
        db.refresh(row)
        self.invalidate(row.tenant_id, row.uuid)
        return row

    @staticmethod
    def _check_lock(row: Agent, expected_version: int) -> None:
        if row.lock_version != expected_version:
            raise HTTPException(
                409,
                {
                    "code": "VERSION_CONFLICT",
                    "message": "Agent was modified by another actor",
                },
            )

    @staticmethod
    def _transition(row: Agent, action: str) -> None:
        if row.lifecycle_status not in LIFECYCLE_TRANSITIONS[action]:
            raise HTTPException(
                409,
                {
                    "code": "INVALID_LIFECYCLE_TRANSITION",
                    "message": f"Cannot {action} an agent in {row.lifecycle_status} state",
                },
            )

    def publish(
        self,
        db: Session,
        identity: AgentIdentity,
        public_id: str,
        expected_version: int,
        change_note: str,
    ) -> Agent:
        self._require(identity, "agents.publish")
        row = self._visible(db, identity, public_id)
        self._require_object_access(db, row, identity, "publish")
        self._check_lock(row, expected_version)
        self._transition(row, "publish")
        version = (
            db.query(AgentVersion)
            .filter_by(
                agent_id=row.id,
                tenant_id=row.tenant_id,
                version=row.current_version,
            )
            .first()
        )
        if version is None or not version.instructions.strip():
            raise HTTPException(
                422,
                {
                    "code": "AGENT_CONFIGURATION_INVALID",
                    "message": "Published agents require instructions",
                },
            )
        model = version.model_configuration.get("model")
        if not model and not row.model_configuration_ref:
            raise HTTPException(
                422,
                {
                    "code": "AGENT_CONFIGURATION_INVALID",
                    "message": "Published agents require a model configuration",
                },
            )
        version.published = True
        if change_note:
            version.change_note = change_note
        row.published_version = version.version
        row.lifecycle_status = "published"
        row.status = "PUBLISHED"
        row.published_at = datetime.now(UTC)
        row.lock_version += 1
        row.updated_by = identity.actor_id
        row.updated_at = datetime.now(UTC)
        for assignment in db.query(AgentToolAssignment).filter_by(
            agent_id=row.id, tenant_id=row.tenant_id
        ):
            assignment.agent_version = version.version
        db.add(
            self._event(
                row,
                identity.actor_id,
                "agent.published",
                {"published_version": version.version},
            )
        )
        db.commit()
        db.refresh(row)
        self.invalidate(row.tenant_id, row.uuid)
        return row

    def lifecycle(
        self,
        db: Session,
        identity: AgentIdentity,
        public_id: str,
        action: str,
        expected_version: int,
        *,
        confirmed: bool = False,
    ) -> Agent:
        self._require(identity, f"agents.{action}")
        row = self._visible(db, identity, public_id)
        self._check_lock(row, expected_version)
        self._transition(row, action)
        if action == "enable" and row.published_version is None:
            raise HTTPException(
                409,
                {
                    "code": "PUBLISHED_VERSION_REQUIRED",
                    "message": "Enable requires a published version",
                },
            )
        if action == "archive":
            if not confirmed:
                raise HTTPException(
                    400,
                    {
                        "code": "CONFIRMATION_REQUIRED",
                        "message": "Archiving requires explicit confirmation",
                    },
                )
            dependencies = (
                db.query(RuntimeExecution)
                .filter(RuntimeExecution.agent.in_([row.uuid, row.slug, row.name]))
                .count()
                + db.query(Workflow)
                .filter(Workflow.assigned_agent.in_([row.uuid, row.slug, row.name]))
                .count()
            )
            if dependencies:
                raise HTTPException(
                    409,
                    {
                        "code": "AGENT_HAS_DEPENDENCIES",
                        "message": "Agent is referenced and cannot be archived",
                    },
                )
            row.lifecycle_status = "archived"
            row.archived_at = datetime.now(UTC)
        elif action == "restore":
            row.lifecycle_status = "disabled" if row.published_version else "draft"
            row.archived_at = None
        else:
            row.lifecycle_status = "enabled" if action == "enable" else "disabled"
        row.status = row.lifecycle_status.upper()
        row.lock_version += 1
        row.updated_by = identity.actor_id
        row.updated_at = datetime.now(UTC)
        db.add(
            self._event(
                row,
                identity.actor_id,
                f"agent.{action}d" if action != "disable" else "agent.disabled",
                {"lifecycle_status": row.lifecycle_status},
            )
        )
        db.commit()
        db.refresh(row)
        self.invalidate(row.tenant_id, row.uuid)
        return row

    def versions(
        self, db: Session, identity: AgentIdentity, public_id: str
    ) -> list[AgentVersion]:
        row = self.get(db, identity, public_id)
        return (
            db.query(AgentVersion)
            .filter_by(agent_id=row.id, tenant_id=row.tenant_id)
            .order_by(AgentVersion.version.desc())
            .all()
        )

    def set_tools(
        self,
        db: Session,
        identity: AgentIdentity,
        public_id: str,
        assignments: list[dict[str, Any]],
    ) -> list[AgentToolAssignment]:
        self._require(identity, "agents.tools.manage")
        row = self._visible(db, identity, public_id)
        if row.lifecycle_status != "draft":
            raise HTTPException(
                409,
                {
                    "code": "DRAFT_REQUIRED",
                    "message": "Tool assignments can only be changed on a draft agent",
                },
            )
        for item in assignments:
            version = item.get("version_restriction")
            query = db.query(ToolDefinition).filter(
                or_(
                    ToolDefinition.tenant_id == row.tenant_id,
                    (
                        (ToolDefinition.tenant_id == "default")
                        & (ToolDefinition.registration_source == "native")
                    ),
                ),
                ToolDefinition.name == item["tool_name"],
                ToolDefinition.enabled.is_(True),
                ToolDefinition.active.is_(True),
            )
            if version and version != "active":
                query = query.filter(ToolDefinition.version == version)
            if query.first() is None:
                raise HTTPException(
                    422,
                    {
                        "code": "TOOL_NOT_AUTHORIZED",
                        "message": "Tool is unavailable for this tenant",
                    },
                )
        db.query(AgentToolAssignment).filter_by(
            agent_id=row.id, tenant_id=row.tenant_id
        ).delete(synchronize_session=False)
        rows = [
            AgentToolAssignment(
                agent_id=row.id,
                tenant_id=row.tenant_id,
                agent_version=None,
                added_by=identity.actor_id,
                **item,
            )
            for item in assignments
        ]
        db.add_all(rows)
        db.add(
            self._event(
                row,
                identity.actor_id,
                "agent.tools.updated",
                {"tool_names": [item["tool_name"] for item in assignments]},
            )
        )
        db.commit()
        self.invalidate(row.tenant_id, row.uuid)
        return rows

    def set_knowledge(
        self,
        db: Session,
        identity: AgentIdentity,
        public_id: str,
        assignments: list[dict[str, Any]],
    ) -> list[AgentKnowledgeAssignment]:
        self._require(identity, "agents.knowledge.manage")
        row = self._visible(db, identity, public_id)
        if row.lifecycle_status != "draft":
            raise HTTPException(
                409,
                {
                    "code": "DRAFT_REQUIRED",
                    "message": "Knowledge assignments can only be changed on a draft agent",
                },
            )
        sources: dict[int, KnowledgeSource] = {}
        for item in assignments:
            source = (
                db.query(KnowledgeSource)
                .filter_by(id=item["knowledge_source_id"], tenant_id=row.tenant_id)
                .first()
            )
            if source is None:
                raise HTTPException(
                    404,
                    {
                        "code": "KNOWLEDGE_SOURCE_NOT_FOUND",
                        "message": "Knowledge source not found",
                    },
                )
            if (
                item.get("readiness_required", True)
                and source.readiness_status != "ready"
            ):
                raise HTTPException(
                    409,
                    {
                        "code": "KNOWLEDGE_NOT_READY",
                        "message": "Knowledge source is not ready",
                    },
                )
            sources[source.id] = source
        db.query(AgentKnowledgeAssignment).filter_by(
            agent_id=row.id, tenant_id=row.tenant_id
        ).delete(synchronize_session=False)
        rows = [
            AgentKnowledgeAssignment(
                agent_id=row.id,
                tenant_id=row.tenant_id,
                source_type=sources[item["knowledge_source_id"]].source_type,
                added_by=identity.actor_id,
                **item,
            )
            for item in assignments
        ]
        db.add_all(rows)
        db.add(
            self._event(
                row,
                identity.actor_id,
                "agent.knowledge.updated",
                {"source_ids": list(sources)},
            )
        )
        db.commit()
        return rows

    def set_access(
        self,
        db: Session,
        identity: AgentIdentity,
        public_id: str,
        assignments: list[dict[str, Any]],
    ) -> list[AgentAccessAssignment]:
        self._require(identity, "agents.access.manage")
        row = self._visible(db, identity, public_id)
        db.query(AgentAccessAssignment).filter_by(
            agent_id=row.id, tenant_id=row.tenant_id
        ).delete(synchronize_session=False)
        rows = [
            AgentAccessAssignment(
                agent_id=row.id,
                tenant_id=row.tenant_id,
                added_by=identity.actor_id,
                **item,
            )
            for item in assignments
        ]
        db.add_all(rows)
        db.add(
            self._event(
                row,
                identity.actor_id,
                "agent.access.updated",
                {"assignment_count": len(rows)},
            )
        )
        db.commit()
        return rows

    def assignments(
        self,
        db: Session,
        identity: AgentIdentity,
        public_id: str,
        kind: str,
    ) -> list[Any]:
        permission = {
            "tools": "agents.tools.manage",
            "knowledge": "agents.knowledge.manage",
            "access": "agents.access.manage",
        }[kind]
        self._require(identity, permission)
        row = self._visible(db, identity, public_id)
        model = {
            "tools": AgentToolAssignment,
            "knowledge": AgentKnowledgeAssignment,
            "access": AgentAccessAssignment,
        }[kind]
        return db.query(model).filter_by(agent_id=row.id, tenant_id=row.tenant_id).all()

    def remove_assignment(
        self,
        db: Session,
        identity: AgentIdentity,
        public_id: str,
        kind: str,
        assignment_id: str,
    ) -> None:
        permission = {
            "tools": "agents.tools.manage",
            "knowledge": "agents.knowledge.manage",
            "access": "agents.access.manage",
        }[kind]
        self._require(identity, permission)
        row = self._visible(db, identity, public_id)
        model = {
            "tools": AgentToolAssignment,
            "knowledge": AgentKnowledgeAssignment,
            "access": AgentAccessAssignment,
        }[kind]
        assignment = (
            db.query(model)
            .filter_by(id=assignment_id, agent_id=row.id, tenant_id=row.tenant_id)
            .first()
        )
        if assignment is None:
            raise HTTPException(
                404,
                {
                    "code": "ASSIGNMENT_NOT_FOUND",
                    "message": "Assignment not found",
                },
            )
        db.delete(assignment)
        db.add(
            self._event(
                row,
                identity.actor_id,
                f"agent.{kind}.assignment_removed",
                {"assignment_id": assignment_id},
            )
        )
        db.commit()
        self.invalidate(row.tenant_id, row.uuid)

    def activity(
        self, db: Session, identity: AgentIdentity, public_id: str
    ) -> list[AgentActivityEvent]:
        row = self.get(db, identity, public_id)
        return (
            db.query(AgentActivityEvent)
            .filter_by(agent_id=row.id, tenant_id=row.tenant_id)
            .order_by(AgentActivityEvent.created_at.desc())
            .all()
        )

    def resolve_runtime(
        self,
        db: Session,
        identity: AgentIdentity,
        public_id: str,
        version: int | None = None,
    ) -> AgentDefinition:
        self._require(identity, "agents.execute")
        row = self._visible(db, identity, public_id)
        self._require_object_access(db, row, identity, "execute")
        if row.lifecycle_status != "enabled" or row.published_version is None:
            raise HTTPException(
                409,
                {
                    "code": "AGENT_NOT_EXECUTABLE",
                    "message": "Agent is not enabled with a published version",
                },
            )
        resolved = version or row.published_version
        if resolved != row.published_version:
            raise HTTPException(
                409,
                {
                    "code": "VERSION_NOT_PUBLISHED",
                    "message": "Requested version is not published",
                },
            )
        key = (row.tenant_id, row.uuid, resolved)
        tool_assignments = (
            db.query(AgentToolAssignment)
            .filter_by(
                agent_id=row.id,
                tenant_id=row.tenant_id,
                agent_version=resolved,
                enabled=True,
            )
            .all()
        )
        for assignment in tool_assignments:
            catalog = db.query(ToolDefinition).filter(
                or_(
                    ToolDefinition.tenant_id == row.tenant_id,
                    (
                        (ToolDefinition.tenant_id == "default")
                        & (ToolDefinition.registration_source == "native")
                    ),
                ),
                ToolDefinition.name == assignment.tool_name,
                ToolDefinition.enabled.is_(True),
                ToolDefinition.active.is_(True),
            )
            if assignment.version_restriction not in {None, "active"}:
                catalog = catalog.filter(
                    ToolDefinition.version == assignment.version_restriction
                )
            if catalog.first() is None:
                self.invalidate(row.tenant_id, row.uuid)
                raise HTTPException(
                    409,
                    {
                        "code": "ASSIGNED_TOOL_UNAVAILABLE",
                        "message": "An assigned tool is no longer available",
                    },
                )
        knowledge_assignments = (
            db.query(AgentKnowledgeAssignment)
            .filter_by(agent_id=row.id, tenant_id=row.tenant_id, enabled=True)
            .all()
        )
        for knowledge_assignment in knowledge_assignments:
            source = (
                db.query(KnowledgeSource)
                .filter_by(
                    id=knowledge_assignment.knowledge_source_id,
                    tenant_id=row.tenant_id,
                )
                .first()
            )
            if source is None or (
                knowledge_assignment.readiness_required
                and source.readiness_status != "ready"
            ):
                self.invalidate(row.tenant_id, row.uuid)
                raise HTTPException(
                    409,
                    {
                        "code": "ASSIGNED_KNOWLEDGE_UNAVAILABLE",
                        "message": "An assigned knowledge source is unavailable",
                    },
                )
        cached = self._runtime_cache.get(key)
        if cached is not None:
            self._runtime_cache.move_to_end(key)
            return cached
        version_row = (
            db.query(AgentVersion)
            .filter_by(
                agent_id=row.id,
                tenant_id=row.tenant_id,
                version=resolved,
                published=True,
            )
            .first()
        )
        if version_row is None:
            raise HTTPException(
                409,
                {
                    "code": "PUBLISHED_VERSION_MISSING",
                    "message": "Published agent version is unavailable",
                },
            )
        caps = [
            AgentCapability(name=str(item), description=str(item))
            for item in version_row.configuration_snapshot.get("capabilities", [])
        ]
        definition = AgentDefinition(
            id=UUID(row.uuid),
            metadata=AgentMetadata(
                name=row.slug,
                version=str(resolved),
                description=row.description,
                owner=row.owner_id,
                metadata={
                    "tenant_id": row.tenant_id,
                    "instructions": version_row.instructions,
                    "model_configuration": version_row.model_configuration,
                    "planner_configuration": version_row.planner_configuration,
                    "execution_limits": version_row.execution_limits,
                    "tool_discovery_configuration": version_row.tool_discovery_configuration,
                    "tool_assignments": [
                        {
                            "name": item.tool_name,
                            "version": item.version_restriction,
                            "action": item.assignment_action,
                            "risk_mode": item.risk_mode,
                            "approval_required": item.approval_required,
                        }
                        for item in tool_assignments
                    ],
                    "knowledge_source_ids": [
                        item.knowledge_source_id for item in knowledge_assignments
                    ],
                },
            ),
            capabilities=caps,
            status=AgentStatus.READY,
            configuration=AgentConfiguration(
                enabled=True,
                timeout_seconds=int(
                    version_row.execution_limits.get("timeout_seconds", 120)
                ),
                metadata={
                    "agent_id": row.uuid,
                    "agent_version": resolved,
                    "tenant_id": row.tenant_id,
                },
            ),
        )
        self._runtime_cache[key] = definition
        self._runtime_cache.move_to_end(key)
        while len(self._runtime_cache) > self._cache_size:
            self._runtime_cache.popitem(last=False)
        return definition

    def invalidate(self, tenant_id: str, public_id: str) -> None:
        for key in [
            item for item in self._runtime_cache if item[:2] == (tenant_id, public_id)
        ]:
            self._runtime_cache.pop(key, None)


agent_application_service = AgentApplicationService()
