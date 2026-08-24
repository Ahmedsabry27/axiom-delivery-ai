from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.audit.events import append_audit_event
from app.database.models.delivery import (
    CopilotResponseEvidence,
    DeliveryCopilotResponse,
    DeliveryDependency,
    DeliveryDependencyEndpoint,
    DeliveryEvidence,
    DeliveryRecommendation,
    DeliveryWorkItem,
)
from app.delivery.raid_repository import RAIDNotFoundError, RAIDRepository
from app.delivery.read_service import DeliveryReadService
from app.models.conversation import Conversation
from app.models.message import Message


class DeliveryCopilotService:
    """Build and persist a deterministic, evidence-backed sprint answer."""

    def __init__(self, db: Session, tenant_id: str, user_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id

    def sprint_insight(
        self, conversation_id: str, sprint_id: str, question: str
    ) -> dict:
        conversation = self._conversation(conversation_id)
        sprint = DeliveryReadService(
            self.db,
            self.tenant_id,
            self.user_id,
        ).sprint_detail(sprint_id)
        if sprint is None:
            raise LookupError("Sprint not found")

        work_ids = {
            item[0]
            for item in self.db.execute(
                select(DeliveryWorkItem.id).where(
                    DeliveryWorkItem.tenant_id == self.tenant_id,
                    DeliveryWorkItem.sprint_id == sprint_id,
                )
            )
        }
        endpoint_match = or_(
            (DeliveryDependencyEndpoint.entity_type == "SPRINT")
            & (DeliveryDependencyEndpoint.entity_id == sprint_id),
            (DeliveryDependencyEndpoint.entity_type == "WORK_ITEM")
            & (DeliveryDependencyEndpoint.entity_id.in_(work_ids)),
        )
        dependencies = list(
            self.db.scalars(
                select(DeliveryDependency)
                .join(
                    DeliveryDependencyEndpoint,
                    (
                        DeliveryDependencyEndpoint.tenant_id
                        == DeliveryDependency.tenant_id
                    )
                    & (
                        DeliveryDependencyEndpoint.dependency_id
                        == DeliveryDependency.id
                    ),
                )
                .where(
                    DeliveryDependency.tenant_id == self.tenant_id,
                    endpoint_match,
                )
                .distinct()
            )
        )
        dependency_ids = {item.id for item in dependencies}
        evidence_criteria = [
            (DeliveryEvidence.entity_type == "SPRINT")
            & (DeliveryEvidence.entity_id == sprint_id)
        ]
        if work_ids:
            evidence_criteria.append(
                (DeliveryEvidence.entity_type == "WORK_ITEM")
                & (DeliveryEvidence.entity_id.in_(work_ids))
            )
        if dependency_ids:
            evidence_criteria.append(DeliveryEvidence.dependency_id.in_(dependency_ids))
        evidence = list(
            self.db.scalars(
                select(DeliveryEvidence).where(
                    DeliveryEvidence.tenant_id == self.tenant_id,
                    or_(*evidence_criteria),
                )
            )
        )
        recommendations = list(
            self.db.scalars(
                select(DeliveryRecommendation).where(
                    DeliveryRecommendation.tenant_id == self.tenant_id,
                    DeliveryRecommendation.entity_type == "SPRINT",
                    DeliveryRecommendation.entity_id == sprint_id,
                    DeliveryRecommendation.status.not_in(("DISMISSED", "COMPLETED")),
                )
            )
        )

        trace_id = str(uuid4())
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=question,
        )
        self.db.add(user_message)
        self.db.flush()
        confidence = self._confidence(sprint, evidence)
        answer = {
            "sprint": {
                "id": sprint["id"],
                "name": sprint["name"],
                "goal": sprint["goal"],
                "health": sprint["health"],
                "healthScore": sprint["healthScore"],
            },
            "goalConfidence": sprint["healthDimensions"][1]["score"],
            "forecast": sprint["forecastDetail"],
            "primaryRisk": sprint["primaryRisk"],
            "blockedWork": sprint["blockers"],
            "dependencies": [
                {
                    "id": item.id,
                    "name": item.name,
                    "status": item.status,
                    "criticalPath": item.critical_path,
                    "requiredBy": item.required_by_date.isoformat()
                    if item.required_by_date
                    else None,
                }
                for item in dependencies
            ],
            "recommendations": [
                {
                    "id": item.id,
                    "title": item.title,
                    "explanation": item.explanation,
                    "confidence": item.confidence,
                }
                for item in recommendations
            ],
            "evidence": [
                {
                    "id": item.id,
                    "entityType": item.entity_type,
                    "entityId": item.entity_id,
                    "title": item.title,
                    "summary": item.summary,
                    "capturedAt": item.captured_at.isoformat(),
                }
                for item in evidence
            ],
            "confidence": confidence,
            "limitations": sprint["limitations"],
            "externalWrites": False,
        }
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=self._summary(answer),
            response_id=trace_id,
        )
        self.db.add(assistant_message)
        self.db.flush()
        response = DeliveryCopilotResponse(
            tenant_id=self.tenant_id,
            conversation_id=conversation_id,
            user_message_id=str(user_message.id),
            assistant_message_id=str(assistant_message.id),
            sprint_id=sprint_id,
            trace_id=trace_id,
            confidence=confidence,
            response_payload=answer,
            created_by=self.user_id,
        )
        self.db.add(response)
        self.db.flush()
        for item in evidence:
            self.db.add(
                CopilotResponseEvidence(
                    tenant_id=self.tenant_id,
                    response_id=response.id,
                    evidence_id=item.id,
                )
            )
        for action, target_type, target_id, metadata in (
            (
                "delivery.copilot.question.recorded",
                "conversation",
                conversation_id,
                {"message_id": str(user_message.id)},
            ),
            (
                "delivery.copilot.context.resolved",
                "sprint",
                sprint_id,
                {"response_id": response.id},
            ),
            (
                "delivery.copilot.evidence.accessed",
                "copilot_response",
                response.id,
                {"evidence_ids": [item.id for item in evidence]},
            ),
            (
                "delivery.copilot.agent.selected",
                "copilot_response",
                response.id,
                {"agent": "deterministic-sprint-intelligence"},
            ),
            (
                "delivery.copilot.model.selected",
                "copilot_response",
                response.id,
                {
                    "provider": "deterministic",
                    "model": "shared-sprint-intelligence-v1",
                },
            ),
            (
                "delivery.copilot.response.validated",
                "copilot_response",
                response.id,
                {"confidence": confidence},
            ),
            (
                "delivery.copilot.recommendation.generated",
                "copilot_response",
                response.id,
                {"recommendation_ids": [item.id for item in recommendations]},
            ),
        ):
            append_audit_event(
                self.db,
                tenant_id=self.tenant_id,
                actor_id=self.user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                correlation_id=trace_id,
                metadata=metadata,
            )
        self.db.commit()
        return {
            "id": response.id,
            "traceId": trace_id,
            "conversationId": conversation_id,
            "userMessageId": str(user_message.id),
            "assistantMessageId": str(assistant_message.id),
            **answer,
        }

    def raid_insight(
        self, conversation_id: str, question: str, raid_id: str | None = None
    ) -> dict:
        """Persist a structured RAID answer from the shared RAID repository."""
        conversation = self._conversation(conversation_id)
        repository = RAIDRepository(self.db, self.tenant_id, self.user_id)
        if raid_id:
            try:
                details = repository.details(raid_id)
            except RAIDNotFoundError as exc:
                raise LookupError("RAID item not found") from exc
            top_items = [details["item"]]
            evidence = details["evidence"]
            recommendations = details["recommendations"]
            hygiene = [
                finding
                for finding in repository.hygiene()
                if finding["record"] == raid_id
            ]
        else:
            top_items, _ = repository.list(page_size=10, sort="attention")
            evidence = []
            recommendations = []
            hygiene = repository.hygiene()[:10]
        trace_id = str(uuid4())
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=question,
        )
        self.db.add(user_message)
        self.db.flush()
        confidence = round(
            min(0.45 + min(len(evidence), 4) * 0.1 + (0.15 if top_items else 0), 0.9),
            2,
        )
        summary = (
            f"{top_items[0].reference or top_items[0].id} has "
            f"{top_items[0].residual_exposure_band or top_items[0].exposure_band or 'UNKNOWN'} exposure."
            if raid_id and top_items
            else f"{len(top_items)} authorized RAID items were prioritised from persisted records."
        )
        answer = {
            "context": {"raidId": raid_id, "scope": "tenant"},
            "summary": summary,
            "health": top_items[0].residual_exposure_band
            or top_items[0].exposure_band
            or "UNKNOWN"
            if top_items
            else "UNKNOWN",
            "topItems": [
                {
                    "id": item.id,
                    "reference": item.reference,
                    "title": item.name,
                    "type": item.item_type,
                    "status": item.status,
                    "exposure": item.residual_exposure_band
                    or item.exposure_band
                    or "UNKNOWN",
                    "attentionScore": item.attention_score,
                    "attentionReasons": item.attention_reasons,
                }
                for item in top_items
            ],
            "trends": [],
            "hygieneFindings": hygiene,
            "affectedEntities": [
                {
                    "projectId": item.project_id,
                    "sprintId": item.sprint_id,
                    "releaseId": item.release_id,
                    "milestoneId": item.milestone_id,
                }
                for item in top_items
            ],
            "recommendations": [
                {
                    "id": item.id,
                    "title": item.title,
                    "reason": item.explanation,
                    "priority": item.priority,
                    "confidence": item.confidence,
                }
                for item in recommendations
            ],
            "evidence": [
                {
                    "id": item.id,
                    "title": item.title,
                    "summary": item.summary,
                    "sourceType": item.source_type,
                    "capturedAt": item.captured_at.isoformat(),
                }
                for item in evidence
            ],
            "confidence": confidence,
            "limitations": [
                "No trend is asserted without multiple persisted history points"
            ]
            + (["No evidence is linked to this RAID scope"] if not evidence else []),
            "generatedAt": datetime.now(UTC).isoformat(),
            "traceId": trace_id,
            "externalWrites": False,
        }
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=summary,
            response_id=trace_id,
        )
        self.db.add(assistant_message)
        self.db.flush()
        response = DeliveryCopilotResponse(
            tenant_id=self.tenant_id,
            conversation_id=conversation_id,
            user_message_id=str(user_message.id),
            assistant_message_id=str(assistant_message.id),
            sprint_id=None,
            raid_id=raid_id,
            response_type="RAID_INTELLIGENCE",
            trace_id=trace_id,
            confidence=confidence,
            response_payload=answer,
            created_by=self.user_id,
        )
        self.db.add(response)
        self.db.flush()
        for item in evidence:
            self.db.add(
                CopilotResponseEvidence(
                    tenant_id=self.tenant_id,
                    response_id=response.id,
                    evidence_id=item.id,
                )
            )
        append_audit_event(
            self.db,
            tenant_id=self.tenant_id,
            actor_id=self.user_id,
            action="delivery.copilot.raid_question",
            target_type="RAID_ITEM" if raid_id else "RAID_REGISTER",
            target_id=raid_id or self.tenant_id,
            correlation_id=trace_id,
            metadata={
                "response_id": response.id,
                "evidence_ids": [item.id for item in evidence],
                "model": "shared-raid-intelligence-v1",
            },
        )
        self.db.commit()
        return {
            "id": response.id,
            "conversationId": conversation_id,
            "userMessageId": str(user_message.id),
            "assistantMessageId": str(assistant_message.id),
            **answer,
        }

    def _conversation(self, conversation_id: str) -> Conversation:
        try:
            identifier = UUID(conversation_id)
        except ValueError as exc:
            raise LookupError("Conversation not found") from exc
        conversation = self.db.scalar(
            select(Conversation).where(
                Conversation.id == identifier,
                Conversation.tenant_id == self.tenant_id,
                Conversation.user_id == self.user_id,
            )
        )
        if conversation is None:
            raise LookupError("Conversation not found")
        return conversation

    @staticmethod
    def _confidence(sprint: dict, evidence: list[DeliveryEvidence]) -> float:
        base = 0.55
        evidence_credit = min(len(evidence), 4) * 0.08
        history_credit = 0 if "Historical" in " ".join(sprint["limitations"]) else 0.1
        return round(min(base + evidence_credit + history_credit, 0.95), 2)

    @staticmethod
    def _summary(answer: dict) -> str:
        return (
            f"{answer['sprint']['name']} is {answer['sprint']['health']}. "
            f"Forecast: {answer['forecast']['completed_points']} points; "
            f"primary risk: {answer['primaryRisk']}. Confidence {answer['confidence']:.0%}."
        )
