from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.contracts.tool import Tool
from app.contracts.tool_models import ExecutionContext, ToolMetadata, ToolResult
from app.database.base import Base
from app.database.models.audit import AuditLog
from app.database.models.tool_discovery import ToolGovernancePolicy
from app.governance.clarifications import consume_clarification, create_clarification
from app.governance.workflows import consume_approval, create_approval, decide_approval
from app.tool_discovery.governance import validate_conditions
from app.tool_sdk.errors import (
    InvalidToolInputError,
    PermissionDeniedError,
    UnsafeOperationError,
)


class GovernedTool(Tool):
    metadata = ToolMetadata(
        name="deployment_report",
        display_name="Deployment Report",
        description="Create a deployment report",
        category="operations",
        provider="internal",
        version="1.0.0",
        permissions=("deployment.report.create",),
        risk_level="write",
        parameters={
            "type": "object",
            "properties": {
                "environment": {"type": "string"},
                "start": {"type": "string"},
            },
            "required": ["environment", "start"],
            "additionalProperties": False,
        },
    )

    async def execute(self, input_data, context):
        return ToolResult.succeeded(input_data)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def context(actor="requester", tenant="tenant-a", **updates):
    base = ExecutionContext(
        actor_id=actor, tenant_id=tenant, permissions={"deployment.report.create"}
    )
    return base.model_copy(update=updates)


def policy(db):
    row = ToolGovernancePolicy(
        tenant_id="tenant-a",
        name="Production approval",
        version=3,
        lifecycle="active",
        conditions=[],
        actions={"approver_role": "operator", "separation_of_duties": True},
        decision="approval_required",
        created_by="admin",
        updated_by="admin",
    )
    db.add(row)
    db.commit()
    return row


def approved_request(db):
    governed = GovernedTool()
    binding = policy(db)
    row, token = create_approval(
        db,
        tool=governed,
        normalized_input={"environment": "prod", "start": "today"},
        context=context(),
        policy_ids=[binding.id],
    )
    approver = context(
        actor="operator", permissions={"approvals.approve"}, roles={"operator"}
    )
    decide_approval(db, row, approver, "approve", "change window verified")
    return governed, binding, row, token


def test_authorized_one_time_approval_and_audit(db):
    governed, binding, row, token = approved_request(db)
    consumed = consume_approval(
        db,
        request_id=row.id,
        token=token,
        tool=governed,
        normalized_input={"environment": "prod", "start": "today"},
        context=context(),
        policy_ids=[binding.id],
    )
    assert consumed.status == "consumed"
    with pytest.raises(UnsafeOperationError):
        consume_approval(
            db,
            request_id=row.id,
            token=token,
            tool=governed,
            normalized_input={"environment": "prod", "start": "today"},
            context=context(),
            policy_ids=[binding.id],
        )
    assert {event.action for event in db.query(AuditLog).all()} >= {
        "approval.created",
        "approval.approved",
        "approval.consumed",
    }


def test_approval_rejects_unauthorized_self_and_cross_tenant(db):
    governed = GovernedTool()
    binding = policy(db)
    row, _ = create_approval(
        db,
        tool=governed,
        normalized_input={"environment": "prod", "start": "today"},
        context=context(),
        policy_ids=[binding.id],
    )
    with pytest.raises(PermissionDeniedError):
        decide_approval(db, row, context(), "approve", "self")
    with pytest.raises(PermissionDeniedError):
        decide_approval(
            db,
            row,
            context(
                actor="other",
                tenant="tenant-b",
                permissions={"approvals.approve"},
                roles={"operator"},
            ),
            "approve",
            "wrong tenant",
        )


@pytest.mark.parametrize("mutation", ["expired", "denied", "revoked"])
def test_non_approved_states_cannot_resume(db, mutation):
    governed, binding, row, token = approved_request(db)
    if mutation == "expired":
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    elif mutation == "denied":
        row.status = "denied"
    else:
        row.status = "revoked"
        row.revoked_at = datetime.now(UTC)
    db.commit()
    with pytest.raises(UnsafeOperationError):
        consume_approval(
            db,
            request_id=row.id,
            token=token,
            tool=governed,
            normalized_input={"environment": "prod", "start": "today"},
            context=context(),
            policy_ids=[binding.id],
        )


def test_approval_binding_mismatches_fail(db):
    governed, binding, row, token = approved_request(db)
    with pytest.raises(UnsafeOperationError):
        consume_approval(
            db,
            request_id=row.id,
            token=token,
            tool=governed,
            normalized_input={"environment": "other", "start": "today"},
            context=context(),
            policy_ids=[binding.id],
        )
    binding.version += 1
    db.commit()
    with pytest.raises(UnsafeOperationError):
        consume_approval(
            db,
            request_id=row.id,
            token=token,
            tool=governed,
            normalized_input={"environment": "prod", "start": "today"},
            context=context(),
            policy_ids=[binding.id],
        )


def test_clarification_validates_binding_expiry_and_replay(db):
    governed = GovernedTool()
    row, token = create_clarification(
        db,
        discovery_id="discovery-1",
        tool=governed,
        context=context(),
        known_values={"environment": "prod"},
        missing_fields=["start"],
        alternatives=[],
    )
    db.commit()
    with pytest.raises(UnsafeOperationError):
        consume_clarification(
            db,
            row=row,
            token=token,
            response={"environment": "other", "start": "today"},
            context=context(),
        )
    with pytest.raises(InvalidToolInputError):
        consume_clarification(db, row=row, token=token, response={}, context=context())
    assert consume_clarification(
        db, row=row, token=token, response={"start": "today"}, context=context()
    ) == {"environment": "prod", "start": "today"}
    with pytest.raises(UnsafeOperationError):
        consume_clarification(
            db, row=row, token=token, response={"start": "tomorrow"}, context=context()
        )


def test_audit_events_are_append_only(db):
    governed = GovernedTool()
    binding = policy(db)
    create_approval(
        db,
        tool=governed,
        normalized_input={"environment": "prod", "start": "today"},
        context=context(),
        policy_ids=[binding.id],
    )
    event = db.query(AuditLog).first()
    event.action = "tampered"
    with pytest.raises(ValueError, match="append-only"):
        db.commit()


def test_complete_governance_validation():
    validate_conditions(
        [
            {"field": "user", "operator": "not_equals", "value": "blocked"},
            {"field": "cost", "operator": "lte", "value": 2.5},
            {"field": "execution_count", "operator": "gte", "value": 3},
            {
                "field": "time",
                "operator": "within_schedule",
                "value": {
                    "days": [0, 1],
                    "start": "09:00",
                    "end": "17:00",
                    "timezone": "UTC",
                },
            },
        ]
    )
    with pytest.raises(ValueError, match="Unknown governance field"):
        validate_conditions([{"field": "password", "operator": "equals", "value": "x"}])
    with pytest.raises(ValueError, match="Contradictory"):
        validate_conditions(
            [
                {"field": "tool", "operator": "equals", "value": "a"},
                {"field": "tool", "operator": "equals", "value": "b"},
            ]
        )
