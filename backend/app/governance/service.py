from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.application_service import AgentIdentity
from app.audit.events import append_audit_event
from app.database.models.audit import AuditLog
from app.database.models.governance import (
    AccessReview,
    AIIncident,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
    GovernancePolicy,
    GovernedModel,
    ModelPrice,
)

POLICY_CATEGORIES = {
    "AI_USAGE",
    "MODEL_ALLOWLIST",
    "DATA_ACCESS",
    "EVIDENCE_REQUIREMENT",
    "ACTION_RISK",
    "APPROVAL",
    "TOOL_PERMISSION",
    "RETENTION",
    "COST_BUDGET",
    "EVALUATION_THRESHOLD",
    "OUTPUT_SAFETY",
    "INCIDENT_RESPONSE",
}
POLICY_STATUSES = {
    "DRAFT",
    "PENDING_APPROVAL",
    "ACTIVE",
    "SUPERSEDED",
    "RETIRED",
    "EXPIRED",
}
MODEL_STATUSES = {"DRAFT", "APPROVED", "ACTIVE", "DEPRECATED", "DISABLED", "BLOCKED"}
HIGH_RISK_PERMISSIONS = {
    "approvals.approve",
    "actions.execute",
    "actions.verify",
    "policies.manage",
    "models.manage",
    "audit.read_sensitive",
    "budgets.manage",
    "tenant.admin",
}
PERMISSION_CATALOGUE = [
    ("delivery.read", "Read delivery records", "LOW", "Delivery"),
    ("sprints.manage", "Manage sprint intelligence", "MEDIUM", "Sprint"),
    ("raid.manage", "Manage RAID records", "MEDIUM", "RAID"),
    ("dependencies.manage", "Manage dependencies", "MEDIUM", "Dependencies"),
    ("meetings.manage", "Manage meeting intelligence", "MEDIUM", "Meetings"),
    ("releases.decide", "Record release decisions", "HIGH", "Releases"),
    ("evidence.read", "Read authorized evidence", "MEDIUM", "Evidence"),
    ("runtime.execute", "Invoke AI Copilot", "MEDIUM", "Copilot"),
    ("agents.update", "Manage agent versions", "HIGH", "Agents"),
    ("actions.execute", "Execute approved actions", "HIGH", "Actions"),
    ("actions.verify", "Verify action outcomes", "HIGH", "Actions"),
    ("approvals.approve", "Approve consequential actions", "HIGH", "Approvals"),
    ("policies.manage", "Create and submit policies", "HIGH", "Policies"),
    ("policies.activate", "Activate approved policies", "HIGH", "Policies"),
    ("models.manage", "Manage governed models", "HIGH", "Models"),
    ("audit.read", "Read tenant audit events", "MEDIUM", "Audit"),
    ("audit.read_sensitive", "Read sensitive audit fields", "HIGH", "Audit"),
    ("evaluations.manage", "Run governed evaluations", "HIGH", "Evaluations"),
    ("budgets.manage", "Manage AI budgets", "HIGH", "Costs"),
    ("incidents.manage", "Manage AI incidents", "HIGH", "Administration"),
    ("retention.manage", "Preview retention actions", "HIGH", "Administration"),
    ("tenant.admin", "Administer tenant controls", "CRITICAL", "Administration"),
]
ROLE_MATRIX = {
    "governance-admin": {item[0] for item in PERMISSION_CATALOGUE},
    "auditor": {"audit.read", "audit.read_sensitive", "delivery.read"},
    "delivery-manager": {
        "delivery.read",
        "sprints.manage",
        "raid.manage",
        "dependencies.manage",
        "releases.decide",
    },
    "ai-operator": {
        "runtime.execute",
        "models.manage",
        "evaluations.manage",
        "incidents.manage",
    },
}


def require(identity: AgentIdentity, permission: str, *, human: bool = False) -> None:
    if not identity.allows(permission):
        raise HTTPException(
            403,
            {
                "code": "PERMISSION_DENIED",
                "message": f"{permission} permission is required",
            },
        )
    if human and identity.subject_type != "user":
        raise HTTPException(
            403,
            {
                "code": "HUMAN_AUTHORIZATION_REQUIRED",
                "message": "A human identity is required",
            },
        )


def visible_policy(
    db: Session, identity: AgentIdentity, policy_id: str
) -> GovernancePolicy:
    row = (
        db.query(GovernancePolicy)
        .filter(GovernancePolicy.id == policy_id)
        .filter(
            (GovernancePolicy.tenant_id == identity.tenant_id)
            | (GovernancePolicy.tenant_id.is_(None))
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            404, {"code": "POLICY_NOT_FOUND", "message": "Policy not found"}
        )
    return row


class GovernancePolicyService:
    def list(self, db: Session, identity: AgentIdentity) -> list[GovernancePolicy]:
        require(identity, "policies.manage")
        return (
            db.query(GovernancePolicy)
            .filter(
                (GovernancePolicy.tenant_id == identity.tenant_id)
                | (GovernancePolicy.tenant_id.is_(None))
            )
            .order_by(
                GovernancePolicy.priority,
                GovernancePolicy.name,
                GovernancePolicy.version.desc(),
            )
            .all()
        )

    def create(
        self, db: Session, identity: AgentIdentity, data: dict
    ) -> GovernancePolicy:
        require(identity, "policies.manage", human=True)
        category = data["category"]
        if category not in POLICY_CATEGORIES:
            raise HTTPException(
                422,
                {
                    "code": "INVALID_POLICY_CATEGORY",
                    "message": "Unsupported policy category",
                },
            )
        tenant_id = (
            None
            if data.get("global_scope") and identity.allows("tenant.admin")
            else identity.tenant_id
        )
        policy_key = data.get("policy_key") or data["name"].lower().replace(" ", "-")
        version = (
            db.query(func.max(GovernancePolicy.version))
            .filter_by(tenant_id=tenant_id, policy_key=policy_key)
            .scalar()
            or 0
        ) + 1
        row = GovernancePolicy(
            tenant_id=tenant_id,
            policy_key=policy_key,
            name=data["name"],
            description=data.get("description", ""),
            category=category,
            version=version,
            status="DRAFT",
            priority=data.get("priority", 100),
            conditions=data.get("conditions", {}),
            effect=data.get("effect", {}),
            reason_codes=data.get("reason_codes", []),
            review_date=data.get("review_date"),
            created_by=identity.actor_id,
            created_at=datetime.now(UTC),
            supersedes_id=data.get("supersedes_id"),
        )
        db.add(row)
        db.flush()
        append_audit_event(
            db,
            tenant_id=identity.tenant_id,
            actor_id=identity.actor_id,
            action="policy.created",
            target_type="governance_policy",
            target_id=row.id,
            after={"policy_key": policy_key, "version": version, "status": "DRAFT"},
        )
        db.commit()
        db.refresh(row)
        return row

    def update_draft(
        self, db: Session, identity: AgentIdentity, policy_id: str, data: dict
    ) -> GovernancePolicy:
        require(identity, "policies.manage", human=True)
        row = visible_policy(db, identity, policy_id)
        if row.status == "ACTIVE":
            data = {
                **data,
                "policy_key": row.policy_key,
                "category": row.category,
                "supersedes_id": row.id,
                "name": data.get("name", row.name),
            }
            return self.create(db, identity, data)
        if row.status != "DRAFT" or row.tenant_id != identity.tenant_id:
            raise HTTPException(
                409,
                {
                    "code": "POLICY_IMMUTABLE",
                    "message": "Only tenant draft policies can be edited",
                },
            )
        for field in (
            "name",
            "description",
            "priority",
            "conditions",
            "effect",
            "reason_codes",
            "review_date",
        ):
            if field in data:
                setattr(row, field, data[field])
        row.state_version += 1
        db.commit()
        db.refresh(row)
        return row

    def submit(
        self, db: Session, identity: AgentIdentity, policy_id: str
    ) -> GovernancePolicy:
        require(identity, "policies.manage", human=True)
        row = visible_policy(db, identity, policy_id)
        if row.status != "DRAFT":
            raise HTTPException(
                409,
                {
                    "code": "INVALID_POLICY_STATE",
                    "message": "Only drafts can be submitted",
                },
            )
        row.status = "PENDING_APPROVAL"
        row.state_version += 1
        append_audit_event(
            db,
            tenant_id=identity.tenant_id,
            actor_id=identity.actor_id,
            action="policy.submitted",
            target_type="governance_policy",
            target_id=row.id,
        )
        db.commit()
        db.refresh(row)
        return row

    def activate(
        self, db: Session, identity: AgentIdentity, policy_id: str
    ) -> GovernancePolicy:
        require(identity, "policies.activate", human=True)
        row = visible_policy(db, identity, policy_id)
        if row.status != "PENDING_APPROVAL":
            raise HTTPException(
                409,
                {
                    "code": "INVALID_POLICY_STATE",
                    "message": "Policy is not awaiting approval",
                },
            )
        if row.created_by == identity.actor_id:
            raise HTTPException(
                403,
                {
                    "code": "SELF_APPROVAL_FORBIDDEN",
                    "message": "Policy author cannot activate the policy",
                },
            )
        current = (
            db.query(GovernancePolicy)
            .filter_by(
                tenant_id=row.tenant_id, policy_key=row.policy_key, status="ACTIVE"
            )
            .all()
        )
        for prior in current:
            prior.status = "SUPERSEDED"
            prior.retired_at = datetime.now(UTC)
        row.status = "ACTIVE"
        row.approved_by = identity.actor_id
        row.activated_at = datetime.now(UTC)
        row.effective_from = row.effective_from or row.activated_at
        row.state_version += 1
        append_audit_event(
            db,
            tenant_id=identity.tenant_id,
            actor_id=identity.actor_id,
            action="policy.activated",
            target_type="governance_policy",
            target_id=row.id,
            policy_id=row.id,
            policy_version=row.version,
        )
        db.commit()
        db.refresh(row)
        return row

    def retire(
        self, db: Session, identity: AgentIdentity, policy_id: str
    ) -> GovernancePolicy:
        require(identity, "policies.activate", human=True)
        row = visible_policy(db, identity, policy_id)
        if row.status not in {"ACTIVE", "PENDING_APPROVAL"}:
            raise HTTPException(
                409,
                {"code": "INVALID_POLICY_STATE", "message": "Policy cannot be retired"},
            )
        row.status = "RETIRED"
        row.retired_at = datetime.now(UTC)
        row.state_version += 1
        db.commit()
        db.refresh(row)
        return row

    def simulate(
        self, db: Session, identity: AgentIdentity, policy_id: str, scenario: dict
    ) -> dict:
        require(identity, "policies.manage")
        draft = visible_policy(db, identity, policy_id)
        if draft.status not in {"DRAFT", "PENDING_APPROVAL"}:
            raise HTTPException(
                409,
                {
                    "code": "SIMULATION_REQUIRES_DRAFT",
                    "message": "Simulation requires a draft policy",
                },
            )
        active = (
            db.query(GovernancePolicy)
            .filter_by(
                tenant_id=draft.tenant_id, policy_key=draft.policy_key, status="ACTIVE"
            )
            .first()
        )
        proposed = self._evaluate(draft, scenario)
        current = (
            self._evaluate(active, scenario)
            if active
            else {"decision": "NO_ACTIVE_POLICY", "reason_codes": []}
        )
        return {
            "current_decision": current,
            "proposed_decision": proposed,
            "changed_behavior": current != proposed,
            "affected": scenario.get("targets", []),
            "conflicts": [],
            "warnings": [] if draft.conditions else ["Policy has no conditions"],
        }

    @staticmethod
    def _evaluate(policy: GovernancePolicy | None, scenario: dict) -> dict:
        if policy is None:
            return {"decision": "NO_ACTIVE_POLICY", "reason_codes": []}
        conditions = policy.conditions or {}
        matches = all(scenario.get(key) == value for key, value in conditions.items())
        return {
            "decision": policy.effect.get("decision", "ALLOW")
            if matches
            else "NOT_APPLICABLE",
            "reason_codes": policy.reason_codes,
            "policy_id": policy.id,
            "policy_version": policy.version,
        }


class AuditIntegrityService:
    @staticmethod
    def verify(db: Session, identity: AgentIdentity) -> dict:
        require(identity, "audit.read")
        rows = (
            db.query(AuditLog)
            .filter_by(tenant_id=identity.tenant_id)
            .filter(AuditLog.integrity_hash.is_not(None))
            .order_by(AuditLog.id)
            .all()
        )
        previous = "0" * 64
        failures = []
        for row in rows:
            expected = hashlib.sha256(
                (previous + (row.canonical_payload or "")).encode()
            ).hexdigest()
            if row.previous_hash != previous or row.integrity_hash != expected:
                failures.append(row.event_id or str(row.id))
            previous = row.integrity_hash or previous
        return {
            "tenant_id": identity.tenant_id,
            "event_count": len(rows),
            "valid": not failures,
            "failures": failures,
            "trust_anchor": "database-local hash chain; no externally protected anchor",
        }


class ModelRegistryService:
    @staticmethod
    def active(
        db: Session, identity: AgentIdentity, model_id: str, classification: str
    ) -> GovernedModel:
        row = (
            db.query(GovernedModel)
            .filter_by(id=model_id)
            .filter(
                (GovernedModel.tenant_id == identity.tenant_id)
                | (GovernedModel.tenant_id.is_(None))
            )
            .first()
        )
        if (
            row is None
            or row.status != "ACTIVE"
            or classification not in (row.allowed_data_classifications or [])
        ):
            raise HTTPException(
                403,
                {
                    "code": "MODEL_NOT_ALLOWED",
                    "message": "Model is not approved for this use",
                },
            )
        return row


class CostCalculationService:
    @staticmethod
    def calculate(
        input_tokens: int | None, output_tokens: int | None, price: ModelPrice | None
    ) -> dict:
        if price is None or input_tokens is None or output_tokens is None:
            return {
                "input_cost": None,
                "output_cost": None,
                "total_cost": None,
                "currency": None,
                "estimated": None,
            }
        million = Decimal(1_000_000)
        input_cost = (
            Decimal(input_tokens) * price.input_cost_per_million / million
        ).quantize(Decimal("0.00000001"))
        output_cost = (
            Decimal(output_tokens) * price.output_cost_per_million / million
        ).quantize(Decimal("0.00000001"))
        return {
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": input_cost + output_cost,
            "currency": price.currency,
            "estimated": False,
        }


class EvaluationRunnerService:
    @staticmethod
    def run(
        db: Session,
        identity: AgentIdentity,
        dataset: EvaluationDataset,
        model: GovernedModel,
    ) -> EvaluationRun:
        require(identity, "evaluations.manage", human=True)
        if dataset.status != "APPROVED" or model.status != "ACTIVE":
            raise HTTPException(
                409,
                {
                    "code": "EVALUATION_INPUT_NOT_APPROVED",
                    "message": "Dataset and model must be approved",
                },
            )
        now = datetime.now(UTC)
        run = EvaluationRun(
            tenant_id=identity.tenant_id,
            dataset_id=dataset.id,
            dataset_version=dataset.version,
            model_id=model.id,
            status="COMPLETED",
            scores={},
            failures=[],
            trace_ids=[],
            started_at=now,
            completed_at=now,
        )
        db.add(run)
        db.flush()
        passed = 0
        for case in dataset.cases:
            checks = case.get("checks", {})
            result_pass = all(bool(value) for value in checks.values())
            reasons = [key for key, value in checks.items() if not value]
            db.add(
                EvaluationResult(
                    run_id=run.id,
                    tenant_id=identity.tenant_id,
                    test_case_id=str(case.get("id")),
                    score=Decimal("1") if result_pass else Decimal("0"),
                    passed=result_pass,
                    reason_codes=reasons,
                    actual_behavior_summary=case.get(
                        "actual_behavior_summary", "Deterministic checks only"
                    ),
                    evidence_validation=case.get("evidence_validation", {}),
                    failure_category=reasons[0] if reasons else None,
                )
            )
            passed += int(result_pass)
        total = len(dataset.cases)
        run.scores = {
            "pass_rate": passed / total if total else None,
            "passed": passed,
            "total": total,
        }
        run.failures = [] if passed == total else ["DETERMINISTIC_GATE_FAILED"]
        db.commit()
        db.refresh(run)
        return run


def governance_overview(db: Session, identity: AgentIdentity) -> dict:
    require(identity, "policies.manage")
    now = datetime.now(UTC)
    policies = (
        db.query(GovernancePolicy)
        .filter(
            (GovernancePolicy.tenant_id == identity.tenant_id)
            | (GovernancePolicy.tenant_id.is_(None))
        )
        .all()
    )
    active = [p for p in policies if p.status == "ACTIVE"]
    due_reviews = (
        db.query(AccessReview)
        .filter_by(tenant_id=identity.tenant_id)
        .filter(
            AccessReview.status != "CLOSED",
            AccessReview.due_at <= now + timedelta(days=30),
        )
        .count()
    )
    incidents = (
        db.query(AIIncident)
        .filter_by(tenant_id=identity.tenant_id)
        .filter(AIIncident.status.notin_(["RESOLVED", "CLOSED"]))
        .count()
    )
    integrity = AuditIntegrityService.verify(db, identity)
    return {
        "summary": {
            "policy_compliance": None
            if not policies
            else round(len(active) / len(policies) * 100, 1),
            "open_governance_findings": incidents,
            "access_reviews_due": due_reviews,
            "approval_compliance": None,
            "audit_coverage": 100
            if integrity["valid"] and integrity["event_count"]
            else None,
        },
        "attention": [{"type": "AUDIT_INTEGRITY_FAILURE", "severity": "CRITICAL"}]
        if not integrity["valid"]
        else [],
        "human_oversight": {
            "recommendations_generated": None,
            "proposed_actions": None,
            "approval_required_actions": None,
            "rejected_proposals": None,
            "self_approval_attempts_blocked": None,
            "execution_failures": None,
            "verification_failures": None,
            "executed_without_required_approval": 0,
        },
        "sources": [
            "governance_policies",
            "governance_access_reviews",
            "audit_logs",
            "ai_incidents",
        ],
    }


governance_policy_service = GovernancePolicyService()
