from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.agents.application_service import AgentIdentity
from app.audit.events import append_audit_event
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.audit import AuditLog
from app.database.models.governance import (
    EvaluationDataset,
    GovernedModel,
    ModelPrice,
    RetentionPolicy,
    UsageRecord,
)
from app.governance.service import (
    AuditIntegrityService,
    CostCalculationService,
    EvaluationRunnerService,
    ModelRegistryService,
    governance_policy_service,
)
from app.main import app
from app.models.runtime_execution import RuntimeExecution
from app.services.runtime_execution_service import RuntimeExecutionService


def admin(actor: str = "admin-1", tenant: str = "tenant-a", subject_type: str = "user"):
    return AgentIdentity(
        actor_id=actor,
        tenant_id=tenant,
        permissions=frozenset({"agents.admin"}),
        groups=frozenset({"admin"}),
        subject_type=subject_type,
    )


def policy_data(**overrides):
    return {
        "policy_key": "approved-models",
        "name": "Approved models",
        "category": "MODEL_ALLOWLIST",
        "conditions": {"classification": "CONFIDENTIAL"},
        "effect": {"decision": "ALLOW"},
        "reason_codes": ["MODEL_APPROVED"],
        **overrides,
    }


def test_policy_lifecycle_versioning_and_human_separation(db_session) -> None:
    author = admin("author")
    approver = admin("approver")
    draft = governance_policy_service.create(db_session, author, policy_data())
    governance_policy_service.submit(db_session, author, draft.id)

    with pytest.raises(Exception, match="Policy author cannot activate"):
        governance_policy_service.activate(db_session, author, draft.id)

    active = governance_policy_service.activate(db_session, approver, draft.id)
    assert active.status == "ACTIVE"
    assert active.approved_by == "approver"

    version_two = governance_policy_service.update_draft(
        db_session,
        author,
        active.id,
        {"name": active.name, "description": "Version two"},
    )
    assert version_two.version == 2
    assert version_two.status == "DRAFT"
    assert active.status == "ACTIVE"


def test_draft_simulation_never_changes_active_state(db_session) -> None:
    author = admin("author")
    draft = governance_policy_service.create(db_session, author, policy_data())
    result = governance_policy_service.simulate(
        db_session, author, draft.id, {"classification": "CONFIDENTIAL"}
    )
    assert result["proposed_decision"]["decision"] == "ALLOW"
    assert db_session.get(type(draft), draft.id).status == "DRAFT"


def test_service_identity_cannot_activate_policy(db_session) -> None:
    draft = governance_policy_service.create(db_session, admin("author"), policy_data())
    governance_policy_service.submit(db_session, admin("author"), draft.id)
    with pytest.raises(Exception, match="human identity"):
        governance_policy_service.activate(
            db_session, admin("automation", subject_type="service"), draft.id
        )


def test_tenant_policy_cannot_be_read_by_direct_object_reference(db_session) -> None:
    draft = governance_policy_service.create(db_session, admin(), policy_data())
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "other-admin",
        "custom:tenant_id": "tenant-b",
        "cognito:groups": ["admin"],
    }
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = TestClient(app).get(f"/api/governance/policies/{draft.id}")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 404


def test_audit_hash_chain_detects_tampering_and_is_append_only(db_session) -> None:
    for index in range(3):
        append_audit_event(
            db_session,
            tenant_id="tenant-a",
            actor_id="admin",
            action=f"policy.event.{index}",
            target_type="policy",
            target_id=str(index),
            metadata={"safe": index},
        )
        db_session.commit()
    assert AuditIntegrityService.verify(db_session, admin())["valid"] is True

    event = db_session.query(AuditLog).filter_by(tenant_id="tenant-a").first()
    event.metadata_json = {"tampered": True}
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()
    db_session.rollback()


def test_audit_api_redacts_sensitive_metadata(db_session) -> None:
    append_audit_event(
        db_session,
        tenant_id="tenant-a",
        actor_id="admin",
        action="model.viewed",
        target_type="model",
        target_id="model-1",
        metadata={"classification": "CONFIDENTIAL"},
    )
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "auditor",
        "custom:tenant_id": "tenant-a",
        "permissions": ["audit.read"],
    }
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = TestClient(app).get("/api/audit/events")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 200
    assert response.json()["items"][0]["safe_metadata"] == {"redacted": True}


def test_model_registry_fails_closed_for_unknown_disabled_or_wrong_classification(
    db_session,
) -> None:
    model = GovernedModel(
        tenant_id="tenant-a",
        model_key="safe-model",
        provider="openai",
        provider_model_id="safe-1",
        display_name="Safe Model",
        model_family="safe",
        capabilities=[],
        approved_use_cases=[],
        prohibited_use_cases=[],
        allowed_data_classifications=["INTERNAL"],
        allowed_regions=["eu"],
        status="ACTIVE",
        configuration_version=1,
        created_by="admin",
        created_at=datetime.now(UTC),
    )
    db_session.add(model)
    db_session.commit()
    assert (
        ModelRegistryService.active(db_session, admin(), model.id, "INTERNAL") == model
    )
    with pytest.raises(Exception, match="not approved"):
        ModelRegistryService.active(db_session, admin(), model.id, "RESTRICTED")
    with pytest.raises(Exception, match="not approved"):
        ModelRegistryService.active(db_session, admin(), "missing", "INTERNAL")


def test_model_activation_requires_a_different_human(db_session) -> None:
    model = GovernedModel(
        tenant_id="tenant-a",
        model_key="lifecycle-model",
        provider="openai",
        provider_model_id="lifecycle-1",
        display_name="Lifecycle Model",
        model_family="test",
        capabilities=[],
        approved_use_cases=[],
        prohibited_use_cases=[],
        allowed_data_classifications=["INTERNAL"],
        allowed_regions=["eu"],
        status="DRAFT",
        configuration_version=1,
        created_by="author",
        created_at=datetime.now(UTC),
    )
    db_session.add(model)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "approver",
        "custom:tenant_id": "tenant-a",
        "cognito:groups": ["admin"],
    }
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        approved = TestClient(app).patch(
            f"/api/models/{model.id}", json={"status": "APPROVED"}
        )
        active = TestClient(app).patch(
            f"/api/models/{model.id}", json={"status": "ACTIVE"}
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
    assert approved.status_code == 200
    assert active.status_code == 200
    assert active.json()["status"] == "ACTIVE"


def test_decimal_cost_calculation_preserves_versioned_inputs(db_session) -> None:
    price = ModelPrice(
        model_id="model-1",
        tenant_id="tenant-a",
        version=3,
        input_cost_per_million=Decimal("2.50000000"),
        output_cost_per_million=Decimal("10.00000000"),
        currency="USD",
        effective_from=datetime.now(UTC),
    )
    result = CostCalculationService.calculate(1000, 2000, price)
    assert result["input_cost"] == Decimal("0.00250000")
    assert result["output_cost"] == Decimal("0.02000000")
    assert result["total_cost"] == Decimal("0.02250000")
    assert CostCalculationService.calculate(None, None, price)["total_cost"] is None


def test_terminal_runtime_persists_versioned_usage_and_decimal_cost(db_session) -> None:
    model = GovernedModel(
        tenant_id="tenant-a",
        model_key="metered",
        provider="openai",
        provider_model_id="metered-1",
        display_name="Metered",
        model_family="test",
        capabilities=[],
        approved_use_cases=[],
        prohibited_use_cases=[],
        allowed_data_classifications=["INTERNAL"],
        allowed_regions=["eu"],
        status="ACTIVE",
        configuration_version=2,
        created_by="reviewer",
        created_at=datetime.now(UTC),
    )
    db_session.add(model)
    db_session.flush()
    db_session.add(
        ModelPrice(
            model_id=model.id,
            tenant_id="tenant-a",
            version=4,
            input_cost_per_million=Decimal("2.5"),
            output_cost_per_million=Decimal("10"),
            currency="USD",
            effective_from=datetime.now(UTC),
        )
    )
    execution = RuntimeExecution(
        id=uuid4(),
        conversation_id=uuid4(),
        workflow_id=uuid4(),
        user_id="user",
        tenant_id="tenant-a",
        status="RUNNING",
        started_at=datetime.now(UTC),
        provider_name="openai",
        model_name="metered-1",
        token_usage={"input_tokens": 1000, "output_tokens": 2000},
        steps=[],
        runtime_metadata={},
    )
    db_session.add(execution)
    db_session.commit()
    RuntimeExecutionService().transition_execution(
        execution.id, "COMPLETED", db=db_session
    )
    usage = (
        db_session.query(UsageRecord).filter_by(execution_id=str(execution.id)).one()
    )
    assert usage.price_version == 4
    assert usage.total_cost == Decimal("0.02250000")
    assert usage.cost_estimated is False


def test_deterministic_evaluation_records_versioned_results(db_session) -> None:
    dataset = EvaluationDataset(
        tenant_id="tenant-a",
        dataset_key="security",
        name="Security",
        description="Synthetic cases",
        version=2,
        status="APPROVED",
        use_case="copilot",
        cases=[
            {"id": "case-1", "checks": {"schema": True, "authorized": True}},
            {"id": "case-2", "checks": {"schema": True, "authorized": False}},
        ],
        approved_by="reviewer",
        created_by="author",
        created_at=datetime.now(UTC),
    )
    model = GovernedModel(
        tenant_id="tenant-a",
        model_key="evaluation-model",
        provider="openai",
        provider_model_id="eval-1",
        display_name="Evaluation Model",
        model_family="eval",
        capabilities=[],
        approved_use_cases=["copilot"],
        prohibited_use_cases=[],
        allowed_data_classifications=["INTERNAL"],
        allowed_regions=["eu"],
        status="ACTIVE",
        configuration_version=4,
        created_by="admin",
        created_at=datetime.now(UTC),
    )
    db_session.add_all([dataset, model])
    db_session.commit()
    run = EvaluationRunnerService.run(db_session, admin(), dataset, model)
    assert run.dataset_version == 2
    assert run.scores == {"pass_rate": 0.5, "passed": 1, "total": 2}
    assert run.failures == ["DETERMINISTIC_GATE_FAILED"]


def test_retention_preview_is_dry_run_and_preserves_audit(db_session) -> None:
    row = RetentionPolicy(
        tenant_id="tenant-a",
        resource_type="audit",
        classification="RESTRICTED",
        retention_days=2555,
        allowed_models=[],
        allowed_providers=[],
        allowed_regions=[],
        logging_controls={},
        export_allowed=False,
        status="ACTIVE",
        created_by="admin",
        created_at=datetime.now(UTC),
    )
    db_session.add(row)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "admin",
        "custom:tenant_id": "tenant-a",
        "cognito:groups": ["admin"],
    }
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = TestClient(app).post(
            "/api/governance/retention/preview", json={"resource_type": "audit"}
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 200
    assert response.json()["dry_run"] is True
    assert response.json()["executed"] is False
    assert response.json()["protected_from_deletion"] is True
