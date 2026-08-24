from __future__ import annotations

import hashlib

from fastapi import HTTPException
from sqlalchemy import or_

from app.agents.application_service import AgentIdentity
from app.audit.events import append_audit_event
from app.database.models.knowledge import (
    KnowledgeEvidenceReference,
    KnowledgeItem,
    KnowledgeItemVersion,
    KnowledgeRelationship,
)


class KnowledgeService:
    def __init__(self, db, identity: AgentIdentity):
        self.db, self.identity = db, identity

    def require(self, p):
        if not self.identity.allows(p):
            raise HTTPException(
                403,
                {"code": "PERMISSION_DENIED", "message": f"{p} permission is required"},
            )

    def visible(self, id):
        self.require("knowledge.read")
        row = (
            self.db.query(KnowledgeItem)
            .filter_by(tenant_id=self.identity.tenant_id, id=id)
            .first()
        )
        if not row:
            raise HTTPException(
                404,
                {
                    "code": "KNOWLEDGE_NOT_FOUND",
                    "message": "Knowledge item was not found",
                },
            )
        return row

    def list(
        self, search=None, item_type=None, status=None, trust=None, freshness=None
    ):
        self.require("knowledge.read")
        q = self.db.query(KnowledgeItem).filter_by(tenant_id=self.identity.tenant_id)
        if search:
            token = f"%{search.strip()}%"
            q = q.filter(
                or_(
                    KnowledgeItem.title.ilike(token),
                    KnowledgeItem.summary.ilike(token),
                    KnowledgeItem.content.ilike(token),
                )
            )
        for field, value in [
            (KnowledgeItem.item_type, item_type),
            (KnowledgeItem.status, status),
            (KnowledgeItem.trust_status, trust),
            (KnowledgeItem.freshness_status, freshness),
        ]:
            if value:
                q = q.filter(field == value)
        return q.order_by(KnowledgeItem.updated_at.desc(), KnowledgeItem.id).all()

    def create(self, v):
        self.require("knowledge.create")
        fingerprint = hashlib.sha256(v["content"].encode()).hexdigest()
        row = KnowledgeItem(
            tenant_id=self.identity.tenant_id,
            owner_id=v.pop("owner_id", None) or self.identity.actor_id,
            created_by=self.identity.actor_id,
            updated_by=self.identity.actor_id,
            content_fingerprint=fingerprint,
            **v,
        )
        self.db.add(row)
        self.db.flush()
        self.db.add(
            KnowledgeItemVersion(
                tenant_id=row.tenant_id,
                item_id=row.id,
                version_number=1,
                title=row.title,
                summary=row.summary,
                content=row.content,
                content_fingerprint=fingerprint,
                change_summary="Initial version",
                author_id=self.identity.actor_id,
                review_status=row.status,
            )
        )
        append_audit_event(
            self.db,
            tenant_id=row.tenant_id,
            actor_id=self.identity.actor_id,
            action="knowledge.created",
            target_type="knowledge_item",
            target_id=row.id,
            after={"title": row.title, "status": row.status},
        )
        self.db.commit()
        return row

    def update(self, id, v, expected):
        self.require("knowledge.update")
        row = self.visible(id)
        if row.status in {"ARCHIVED", "SUPERSEDED"}:
            raise HTTPException(
                409,
                {
                    "code": "KNOWLEDGE_IMMUTABLE",
                    "message": "Archived or superseded knowledge cannot be edited",
                },
            )
        if row.version != expected:
            raise HTTPException(
                409,
                {
                    "code": "STALE_VERSION",
                    "message": "Knowledge item changed; refresh and retry",
                },
            )
        for key, value in v.items():
            setattr(row, key, value)
        row.version += 1
        row.current_version += 1
        row.updated_by = self.identity.actor_id
        row.content_fingerprint = hashlib.sha256(row.content.encode()).hexdigest()
        self.db.add(
            KnowledgeItemVersion(
                tenant_id=row.tenant_id,
                item_id=row.id,
                version_number=row.current_version,
                title=row.title,
                summary=row.summary,
                content=row.content,
                content_fingerprint=row.content_fingerprint,
                change_summary="Knowledge item updated",
                author_id=self.identity.actor_id,
                review_status=row.status,
            )
        )
        append_audit_event(
            self.db,
            tenant_id=row.tenant_id,
            actor_id=self.identity.actor_id,
            action="knowledge.updated",
            target_type="knowledge_item",
            target_id=row.id,
            after={"version": row.version, "status": row.status},
        )
        self.db.commit()
        return row

    def relationships(self, id):
        self.visible(id)
        return (
            self.db.query(KnowledgeRelationship)
            .filter_by(tenant_id=self.identity.tenant_id, item_id=id)
            .order_by(KnowledgeRelationship.created_at.desc())
            .all()
        )

    def versions(self, id):
        self.visible(id)
        return (
            self.db.query(KnowledgeItemVersion)
            .filter_by(tenant_id=self.identity.tenant_id, item_id=id)
            .order_by(KnowledgeItemVersion.version_number.desc())
            .all()
        )

    def evidence_refs(self, id):
        self.visible(id)
        return (
            self.db.query(KnowledgeEvidenceReference)
            .filter_by(tenant_id=self.identity.tenant_id, item_id=id)
            .all()
        )
