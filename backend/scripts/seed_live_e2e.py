from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.action_center.service import ActionCenterService
from app.agents.application_service import AgentApplicationService, AgentIdentity
from app.auth.e2e import issue_e2e_token
from app.database.models.delivery import (
    DeliveryDependency,
    DeliveryEvidence,
    DeliveryMilestone,
    DeliveryPortfolio,
    DeliveryProgramme,
    DeliveryProject,
    DeliveryRecommendation,
    DeliveryRelease,
    DeliverySprint,
    DeliveryTeam,
    DeliveryWorkItem,
    DetectedRAIDCandidate,
    DetectedRAIDCandidateEvidence,
)
from app.database.session import SessionLocal
from app.delivery.raid_repository import RAIDRepository
from app.delivery.repositories import DependencyRepository


def main() -> None:
    output = Path(os.environ["E2E_STATE_PATH"]).resolve()
    tenant = f"e2e-{uuid4()}"
    actor = f"platform-admin-{uuid4()}"
    claims = {
        "sub": actor,
        "custom:tenant_id": tenant,
        "cognito:groups": ["platform-admin"],
        "permissions": [
            "agents.list",
            "agents.read",
            "agents.create",
            "raid.read",
            "raid.create",
            "raid.update",
            "raid.assign",
            "raid.review",
            "raid.close",
            "raid.manage_evidence",
            "raid.manage_relationships",
            "raid.review_candidates",
            "dependency.read",
            "dependency.create",
            "dependency.update",
            "dependency.analyse",
            "dependency.review_candidates",
        ],
    }
    cross_tenant_claims = {
        "sub": f"cross-tenant-admin-{uuid4()}",
        "custom:tenant_id": f"e2e-other-{uuid4()}",
        "cognito:groups": ["platform-admin"],
        "permissions": [
            "agents.admin",
            "raid.read",
            "raid.manage_evidence",
            "dependency.read",
            "dependency.create",
            "dependency.update",
            "dependency.analyse",
            "meetings.read",
        ],
    }
    requester_id = f"action-requester-{uuid4()}"
    approver_id = f"action-approver-{uuid4()}"
    executor_id = f"action-executor-{uuid4()}"
    verifier_id = f"action-verifier-{uuid4()}"
    requester_claims = {
        "sub": requester_id,
        "custom:tenant_id": tenant,
        "permissions": [
            "actions.create",
            "actions.read",
            "actions.edit",
            "approvals.request",
            "actions.cancel",
            "meetings.read",
            "meetings.create",
            "meetings.analyse",
            "meetings.review",
            "meetings.propose",
        ],
    }
    approver_claims = {
        "sub": approver_id,
        "custom:tenant_id": tenant,
        "permissions": [
            "approvals.read",
            "approvals.read_all",
            "approvals.approve",
            "meetings.read",
        ],
    }
    executor_claims = {
        "sub": executor_id,
        "custom:tenant_id": tenant,
        "permissions": ["actions.read", "actions.read_all", "actions.execute"],
    }
    verifier_claims = {
        "sub": verifier_id,
        "custom:tenant_id": tenant,
        "permissions": ["actions.read", "actions.read_all", "actions.verify"],
    }
    identity = AgentIdentity.from_claims(claims)
    with SessionLocal() as database:
        agent = AgentApplicationService().create(
            database,
            identity,
            {
                "name": "Live E2E Agent",
                "description": "Deterministic disposable browser verification Agent",
                "instructions": "Return only safe deterministic test evidence.",
                "model_configuration": {
                    "provider": "fake-e2e-provider",
                    "model": "deterministic-model",
                },
                "environment_restrictions": ["test"],
            },
        )
        portfolio = DeliveryPortfolio(
            tenant_id=tenant, name="E2E Portfolio", status="ACTIVE"
        )
        database.add(portfolio)
        database.flush()
        programme = DeliveryProgramme(
            tenant_id=tenant,
            name="E2E Programme",
            portfolio_id=portfolio.id,
            status="ACTIVE",
        )
        database.add(programme)
        database.flush()
        project = DeliveryProject(
            tenant_id=tenant,
            name="Payments",
            programme_id=programme.id,
            status="AT_RISK",
        )
        database.add(project)
        database.flush()
        team = DeliveryTeam(
            tenant_id=tenant, name="Phoenix", project_id=project.id, status="ACTIVE"
        )
        database.add(team)
        database.flush()
        sprint = DeliverySprint(
            tenant_id=tenant,
            name="Live Sprint 24",
            project_id=project.id,
            team_id=team.id,
            goal="Ship authenticated payments",
            status="ACTIVE",
            start_date=datetime.now(UTC).date() - timedelta(days=6),
            end_date=datetime.now(UTC).date() + timedelta(days=3),
            original_committed_points=13,
            completed_original_points=5,
            completed_points=5,
            scope_added_points=3,
        )
        database.add(sprint)
        database.flush()
        work = DeliveryWorkItem(
            tenant_id=tenant,
            name="Authentication API",
            project_id=project.id,
            sprint_id=sprint.id,
            status="BLOCKED",
            story_points=8,
            assignee_id=actor,
            goal_critical=True,
            blocked=True,
            blocked_since=datetime.now(UTC) - timedelta(days=4),
        )
        database.add(work)
        database.flush()
        release = DeliveryRelease(
            tenant_id=tenant,
            name="Release 4",
            project_id=project.id,
            status="PLANNED",
            planned_date=datetime.now(UTC).date() + timedelta(days=12),
        )
        database.add(release)
        database.flush()
        milestone = DeliveryMilestone(
            tenant_id=tenant,
            name="Payment launch milestone",
            project_id=project.id,
            release_id=release.id,
            sprint_id=sprint.id,
            description="Synthetic payment launch milestone.",
            status="PLANNED",
            planned_date=datetime.now(UTC).date() + timedelta(days=9),
            forecast_date=datetime.now(UTC).date() + timedelta(days=12),
            critical=True,
        )
        database.add(milestone)
        database.flush()
        today = datetime.now(UTC).date()
        dependency = DeliveryDependency(
            tenant_id=tenant,
            reference="D-018",
            name="Customer API delivery",
            description="Synthetic external API output required by the authenticated payment work item.",
            project_id=project.id,
            dependency_type="EXTERNAL",
            relationship_type="DELIVERS_TO",
            status="BLOCKED",
            impact="CRITICAL",
            priority="CRITICAL",
            critical_path=True,
            owner_id=actor,
            provider_owner_id=actor,
            acknowledged_at=datetime.now(UTC) - timedelta(days=2),
            required_by_date=today + timedelta(days=2),
            committed_resolution_date=today + timedelta(days=1),
            forecast_resolution_date=today + timedelta(days=6),
            blocked_since=datetime.now(UTC) - timedelta(days=4),
            last_reviewed_at=datetime.now(UTC) - timedelta(days=1),
            next_review_date=today + timedelta(days=1),
            external=True,
        )
        DependencyRepository(database, tenant).add_with_endpoints(
            dependency,
            ("EXTERNAL_PARTY", "identity-provider"),
            ("WORK_ITEM", work.id),
        )
        chain = [
            (
                "D-019",
                "Work item to Sprint 24",
                ("WORK_ITEM", work.id),
                ("SPRINT", sprint.id),
            ),
            (
                "D-020",
                "Sprint 24 to launch milestone",
                ("SPRINT", sprint.id),
                ("MILESTONE", milestone.id),
            ),
            (
                "D-021",
                "Launch milestone to Release 4",
                ("MILESTONE", milestone.id),
                ("RELEASE", release.id),
            ),
        ]
        for reference, name, provider, consumer in chain:
            related = DeliveryDependency(
                tenant_id=tenant,
                reference=reference,
                name=name,
                description=f"Synthetic critical-path relationship: {name}.",
                project_id=project.id,
                dependency_type="DELIVERY",
                relationship_type="DELIVERS_TO",
                status="IN_PROGRESS",
                impact="HIGH",
                priority="HIGH",
                critical_path=True,
                owner_id=actor,
                provider_owner_id=actor,
                acknowledged_at=datetime.now(UTC) - timedelta(days=2),
                required_by_date=today + timedelta(days=4),
                committed_resolution_date=today + timedelta(days=3),
                forecast_resolution_date=today + timedelta(days=5),
                last_reviewed_at=datetime.now(UTC) - timedelta(days=1),
            )
            DependencyRepository(database, tenant).add_with_endpoints(
                related, provider, consumer
            )
        evidence = DeliveryEvidence(
            tenant_id=tenant,
            entity_type="DEPENDENCY",
            entity_id=dependency.id,
            dependency_id=dependency.id,
            source_type="STATUS_UPDATE",
            source_system="MANUAL",
            source_record_id="live-identity-delay",
            title="Identity provider delivery delayed",
            summary="The provider missed its committed delivery date by four days.",
        )
        recommendation = DeliveryRecommendation(
            tenant_id=tenant,
            entity_type="SPRINT",
            entity_id=sprint.id,
            title="Escalate the identity provider dependency",
            explanation="Request a dated recovery plan and review sprint scope with the Product Owner.",
            priority="CRITICAL",
            confidence=0.91,
        )
        database.add_all((evidence, recommendation))
        database.flush()
        raid_repository = RAIDRepository(database, tenant, actor)
        raid_records = [
            raid_repository.create(
                {
                    "reference": "R-031",
                    "item_type": "RISK",
                    "name": "Payment API delay",
                    "description": "Synthetic provider capacity constraints threaten the payment API milestone.",
                    "project_id": project.id,
                    "sprint_id": sprint.id,
                    "probability": "ALMOST_CERTAIN",
                    "impact": "CRITICAL",
                    "residual_probability": "ALMOST_CERTAIN",
                    "residual_impact": "CRITICAL",
                    "owner_id": actor,
                    "review_date": today + timedelta(days=2),
                    "due_date": today + timedelta(days=3),
                    "mitigation_plan": "Review fictional provider recovery evidence each day.",
                    "priority": "CRITICAL",
                }
            ),
            raid_repository.create(
                {
                    "reference": "A-014",
                    "item_type": "ASSUMPTION",
                    "name": "UAT environment capacity assumption",
                    "description": "Synthetic UAT capacity is assumed to support peak validation.",
                    "project_id": project.id,
                    "sprint_id": sprint.id,
                    "validation_owner_id": actor,
                    "validation_due_date": today + timedelta(days=4),
                    "validation_method": "Review synthetic capacity-test evidence.",
                }
            ),
            raid_repository.create(
                {
                    "reference": "I-011",
                    "item_type": "ISSUE",
                    "name": "SIT environment instability",
                    "description": "Synthetic intermittent failures are delaying integration validation.",
                    "project_id": project.id,
                    "sprint_id": sprint.id,
                    "severity": "CRITICAL",
                    "owner_id": actor,
                    "due_date": today + timedelta(days=2),
                    "resolution_plan": "Stabilise the fictional environment and rerun the evidence pack.",
                }
            ),
            raid_repository.create(
                {
                    "reference": "D-018",
                    "item_type": "DEPENDENCY",
                    "name": "Identity to Payment API dependency",
                    "description": "Synthetic identity output is required before payment integration can complete.",
                    "project_id": project.id,
                    "sprint_id": sprint.id,
                    "dependency_id": dependency.id,
                    "owner_id": actor,
                    "due_date": today + timedelta(days=2),
                    "impact": "CRITICAL",
                    "critical_path": True,
                }
            ),
            raid_repository.create(
                {
                    "reference": "DEC-007",
                    "item_type": "DECISION",
                    "name": "Authentication approach decision",
                    "description": "A fictional architecture decision is required for the release.",
                    "project_id": project.id,
                    "sprint_id": sprint.id,
                    "decision_owner_id": actor,
                    "due_date": today + timedelta(days=1),
                }
            ),
            raid_repository.create(
                {
                    "reference": "ACT-022",
                    "item_type": "ACTION",
                    "name": "Confirm UAT approval",
                    "description": "Confirm the fictional approval evidence for UAT entry.",
                    "project_id": project.id,
                    "sprint_id": sprint.id,
                    "owner_id": actor,
                    "identified_at": datetime.now(UTC) - timedelta(days=5),
                    "due_date": today - timedelta(days=1),
                }
            ),
        ]
        for raid_record in raid_records:
            raid_repository.link_evidence(raid_record.id, evidence.id)
        raid_repository.add_relationship(
            raid_records[0].id, "SPRINT", sprint.id, "THREATENS"
        )
        candidate = DetectedRAIDCandidate(
            tenant_id=tenant,
            candidate_type="RISK",
            title="Payment certification window",
            description="Synthetic sprint evidence indicates a certification-window risk for human review.",
            confidence=0.86,
            affected_entities=[{"type": "SPRINT", "id": sprint.id}],
            suggested_owner=actor,
            suggested_due_date=today + timedelta(days=5),
            suggested_probability="LIKELY",
            suggested_impact="HIGH",
            possible_duplicates=[],
            limitations=["Single synthetic reporting period"],
            detected_by_agent="axiom-raid-deterministic-detector",
            model="deterministic-rules-v1",
            trace_id=str(uuid4()),
        )
        database.add(candidate)
        database.flush()
        database.add(
            DetectedRAIDCandidateEvidence(
                tenant_id=tenant,
                candidate_id=candidate.id,
                evidence_id=evidence.id,
            )
        )
        action_service = ActionCenterService(
            database, AgentIdentity.from_claims(requester_claims)
        )
        controlled_payload = {
            "project_id": project.id,
            "item_type": "RISK",
            "name": "Expired synthetic approval",
            "description": "This fixture proves expired approvals fail closed.",
            "probability": "POSSIBLE",
            "impact": "HIGH",
            "review_date": (today + timedelta(days=7)).isoformat(),
        }
        expired_action = action_service.create(
            {
                "action_type": "CREATE_RAID_ITEM",
                "title": "Expired action fixture",
                "description": "Synthetic expired approval.",
                "payload": controlled_payload,
                "evidence_ids": [evidence.id],
                "idempotency_key": f"expired-{uuid4()}",
            }
        )
        expired_approval = action_service.submit(expired_action.id, approver_id)
        expired_action.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        expired_approval.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        stale_action = action_service.create(
            {
                "action_type": "CREATE_RAID_ITEM",
                "title": "Stale action fixture",
                "description": "Synthetic stale approval.",
                "payload": {**controlled_payload, "name": "Stale synthetic approval"},
                "evidence_ids": [evidence.id],
                "idempotency_key": f"stale-{uuid4()}",
            }
        )
        stale_approval = action_service.submit(stale_action.id, approver_id)
        stale_action.version += 1
        database.commit()
        seeded_ids = {
            "agent_id": agent.uuid,
            "sprint_id": sprint.id,
            "work_item_id": work.id,
            "dependency_id": dependency.id,
            "evidence_id": evidence.id,
            "recommendation_id": recommendation.id,
            "raid_id": raid_records[0].id,
            "candidate_id": candidate.id,
            "project_id": project.id,
            "milestone_id": milestone.id,
            "release_id": release.id,
            "expired_approval_id": expired_approval.id,
            "stale_approval_id": stale_approval.id,
        }
        database.commit()
    output.write_text(
        json.dumps(
            {
                "token": issue_e2e_token(claims, lifetime_seconds=3600),
                "cross_tenant_token": issue_e2e_token(
                    cross_tenant_claims, lifetime_seconds=3600
                ),
                "requester_token": issue_e2e_token(
                    requester_claims, lifetime_seconds=3600
                ),
                "approver_token": issue_e2e_token(
                    approver_claims, lifetime_seconds=3600
                ),
                "executor_token": issue_e2e_token(
                    executor_claims, lifetime_seconds=3600
                ),
                "verifier_token": issue_e2e_token(
                    verifier_claims, lifetime_seconds=3600
                ),
                "requester_id": requester_id,
                "approver_id": approver_id,
                "executor_id": executor_id,
                "verifier_id": verifier_id,
                "tenant": tenant,
                "actor": actor,
                **seeded_ids,
            }
        )
    )
    output.chmod(0o600)


if __name__ == "__main__":
    main()
