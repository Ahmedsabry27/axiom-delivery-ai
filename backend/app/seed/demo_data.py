from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.models.agent import Agent, AgentVersion
from app.database.models.delivery import (
    DeliveryDefect,
    DeliveryDependency,
    DeliveryDependencyEndpoint,
    DeliveryEvidence,
    DeliveryMilestone,
    DeliveryPortfolio,
    DeliveryProgramme,
    DeliveryProject,
    DeliveryRAIDItem,
    DeliveryRecommendation,
    DeliveryRelease,
    DeliverySprint,
    DeliveryTeam,
    DeliveryWorkItem,
    PortfolioInvestmentSnapshot,
    PortfolioOutcomeLink,
    PortfolioStrategicOutcome,
    ProposedAction,
)
from app.database.models.governance import (
    AIIncident,
    Budget,
    GovernancePolicy,
    GovernedModel,
    UsageRecord,
)
from app.database.models.governance_workflow import ApprovalRequest
from app.database.models.integration import IntegrationConnection
from app.database.models.knowledge_source import KnowledgeSource
from app.database.models.meeting import Meeting, MeetingParticipant
from app.database.models.user import User
from app.database.models.workflow import Workflow
from app.database.session import SessionLocal

DEMO_TENANT = "axiom-demo"
SCENARIO = "enterprise-transformation"
MANIFEST = "AX-DEMO-01"
ALLOWED_ENVIRONMENTS = {"development", "test"}


class DemoSeedError(RuntimeError):
    pass


def stable_id(kind: str, key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"axiom-demo:{SCENARIO}:{kind}:{key}"))


def _dt(day: date, hour: int = 9) -> datetime:
    return datetime.combine(day, time(hour), UTC)


def assert_safe_environment(tenant_id: str) -> None:
    environment = os.getenv("APP_ENV", "development").lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise DemoSeedError("Demo seeding is refused outside development or test")
    if os.getenv("ALLOW_DEMO_SEED", "").lower() != "true":
        raise DemoSeedError("ALLOW_DEMO_SEED=true is required")
    if not tenant_id or tenant_id != DEMO_TENANT:
        raise DemoSeedError("The exact classified demo tenant 'axiom-demo' is required")


def assert_safe_database(db: Session) -> None:
    url = db.get_bind().url
    if url.get_backend_name() == "sqlite":
        return
    if (url.host or "").lower() not in {"localhost", "127.0.0.1", "::1"}:
        raise DemoSeedError("Demo seeding requires a local or SQLite database target")


def _meta(**values) -> dict:
    return {"seed_manifest": MANIFEST, "data_classification": "DEMO", **values}


def _merge(db: Session, model, key: str, **values):
    record = model(
        id=stable_id(model.__tablename__, key), tenant_id=DEMO_TENANT, **values
    )
    return db.merge(record)


PERSONAS = [
    ("eleanor-grant", "Eleanor Grant", "EXECUTIVE_SPONSOR"),
    ("marcus-reed", "Marcus Reed", "PORTFOLIO_DIRECTOR"),
    ("priya-nair", "Priya Nair", "PROGRAMME_MANAGER"),
    ("daniel-foster", "Daniel Foster", "PROGRAMME_MANAGER"),
    ("sofia-bennett", "Sofia Bennett", "PROGRAMME_MANAGER"),
    ("maya-chen", "Maya Chen", "PROJECT_MANAGER"),
    ("oliver-hayes", "Oliver Hayes", "PROJECT_MANAGER"),
    ("nadia-rahman", "Nadia Rahman", "DELIVERY_LEAD"),
    ("liam-carter", "Liam Carter", "RELEASE_MANAGER"),
    ("chloe-martin", "Chloe Martin", "FINANCE_VIEWER"),
    ("grace-wilson", "Grace Wilson", "APPROVER"),
    ("ethan-brooks", "Ethan Brooks", "GOVERNANCE_LEAD"),
    ("aisha-khan", "Aisha Khan", "TEAM_MEMBER"),
    ("noah-turner", "Noah Turner", "RESTRICTED_VIEWER"),
]

PROGRAMMES = [
    (
        "cx",
        "Customer Experience Modernisation",
        "ACTIVE",
        "AMBER",
        "priya-nair",
        Decimal("7200000"),
        Decimal("3350000"),
        Decimal("7550000"),
    ),
    (
        "core",
        "Core Platform Resilience",
        "AT_RISK",
        "RED",
        "daniel-foster",
        Decimal("6800000"),
        Decimal("3400000"),
        Decimal("7350000"),
    ),
    (
        "ops",
        "Operations Automation",
        "ACTIVE",
        "GREEN",
        "sofia-bennett",
        Decimal("4400000"),
        Decimal("1400000"),
        Decimal("4350000"),
    ),
]

PROJECTS = [
    (
        "claims",
        "cx",
        "Digital Claims Portal",
        "AT_RISK",
        "maya-chen",
        "Phoenix",
        Decimal("3000000"),
        Decimal("1480000"),
        Decimal("3220000"),
    ),
    (
        "data",
        "cx",
        "Customer Data Platform",
        "ACTIVE",
        "maya-chen",
        "Horizon",
        Decimal("2400000"),
        Decimal("1120000"),
        Decimal("2450000"),
    ),
    (
        "omnichannel",
        "cx",
        "Omnichannel Service Experience",
        "ACTIVE",
        "priya-nair",
        "Nova",
        Decimal("1800000"),
        Decimal("750000"),
        Decimal("1880000"),
    ),
    (
        "identity",
        "core",
        "Identity Modernisation",
        "BLOCKED",
        "oliver-hayes",
        "Sentinel",
        Decimal("2800000"),
        Decimal("1540000"),
        Decimal("3150000"),
    ),
    (
        "cloud",
        "core",
        "Cloud Platform Migration",
        "AT_RISK",
        "daniel-foster",
        "Atlas",
        Decimal("2400000"),
        Decimal("1210000"),
        Decimal("2550000"),
    ),
    (
        "observability",
        "core",
        "Observability and Resilience",
        "ACTIVE",
        "daniel-foster",
        "Atlas",
        Decimal("1600000"),
        Decimal("650000"),
        Decimal("1650000"),
    ),
    (
        "service-desk",
        "ops",
        "Intelligent Service Desk",
        "ACTIVE",
        "sofia-bennett",
        "FlowOps",
        Decimal("2450000"),
        Decimal("820000"),
        Decimal("2400000"),
    ),
    (
        "finance",
        "ops",
        "Finance Workflow Automation",
        "ACTIVE",
        "sofia-bennett",
        "FlowOps",
        Decimal("1950000"),
        Decimal("580000"),
        Decimal("1950000"),
    ),
]


def seed_demo(db: Session, reference_date: date) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for slug, name, role in PERSONAS:
        email = f"{slug}@demo.axiom.invalid"
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            db.add(User(email=email, name=name, role=role, tenant_id=DEMO_TENANT))
        else:
            user.name, user.role, user.tenant_id = name, role, DEMO_TENANT
        counts["users"] += 1

    agent_profiles = [
        ("Delivery Health Analyst", "enabled", "healthy"),
        ("Sprint Intelligence Agent", "draft", "unknown"),
        ("Release Readiness Analyst", "published", "healthy"),
        ("RAID Analyst", "disabled", "attention"),
        ("Meeting Extraction Agent", "error", "error"),
        ("Executive Reporting Agent", "published", "healthy"),
    ]
    for index, (name, lifecycle, health) in enumerate(agent_profiles):
        slug = name.lower().replace(" ", "-")
        agent = db.scalar(
            select(Agent).where(Agent.tenant_id == DEMO_TENANT, Agent.slug == slug)
        )
        snapshot = {
            "instructions": f"Provide evidence-grounded {name.lower()} insights. Clearly disclose limitations and never perform external mutations.",
            "model_configuration": {
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "fallback": "amazon.nova-lite-v1:0" if index == 2 else None,
            },
            "planner_configuration": {"name": "default", "mode": "safe-demo"},
            "memory_configuration": {"retention": "30_days"},
            "execution_limits": {
                "max_steps": 20,
                "timeout_seconds": 120,
                "cost_limit": 5.0,
                "risk_limit": "read",
                "environments": ["development", "test"],
            },
            "tool_discovery_configuration": {"mode": "assigned_only"},
            "capabilities": [slug.replace("-agent", ""), "evidence-grounding"],
        }
        published = lifecycle in {"enabled", "published", "disabled", "error"}
        values = {
            "uuid": stable_id("agents", slug),
            "tenant_id": DEMO_TENANT,
            "slug": slug,
            "name": name,
            "description": "Fictional governed demonstration agent.",
            "owner_id": "ethan-brooks",
            "lifecycle_status": lifecycle,
            "operational_health": health,
            "current_version": 1,
            "published_version": 1 if published else None,
            "model_configuration_ref": "demo-default-model",
            "planner_configuration": snapshot["planner_configuration"],
            "environment_restrictions": ["development", "test"],
            "configuration": json.dumps(snapshot),
            "created_by": MANIFEST,
            "updated_by": MANIFEST,
            "status": lifecycle.upper(),
            "health": health.upper(),
        }
        if agent is None:
            agent = Agent(**values)
            db.add(agent)
        for field, value in values.items():
            setattr(agent, field, value)
        db.flush()
        version = db.scalar(
            select(AgentVersion).where(
                AgentVersion.tenant_id == DEMO_TENANT,
                AgentVersion.agent_id == agent.id,
                AgentVersion.version == 1,
            )
        )
        version_values = {
            "instructions": snapshot["instructions"],
            "model_configuration": snapshot["model_configuration"],
            "planner_configuration": snapshot["planner_configuration"],
            "memory_configuration": snapshot["memory_configuration"],
            "execution_limits": snapshot["execution_limits"],
            "tool_discovery_configuration": snapshot["tool_discovery_configuration"],
            "configuration_snapshot": snapshot,
            "change_note": "AX-DEMO-01 governed baseline",
            "created_by": MANIFEST,
            "published": published,
        }
        if version is None:
            version = AgentVersion(
                agent_id=agent.id,
                tenant_id=DEMO_TENANT,
                version=1,
                **version_values,
            )
            db.add(version)
        else:
            for field, value in version_values.items():
                setattr(version, field, value)
        counts["agents"] += 1

    for _index, goal in enumerate(
        [
            "Weekly Portfolio Health Review",
            "Meeting-to-Action Review",
            "Release Readiness Assessment",
            "RAID Escalation",
            "Sprint Risk Review",
            "Evidence Freshness Check",
        ]
    ):
        workflow = db.scalar(
            select(Workflow).where(
                Workflow.goal == goal, Workflow.created_by == MANIFEST
            )
        )
        if workflow is None:
            db.add(
                Workflow(
                    goal=goal,
                    description="Safe fictional manual demonstration workflow.",
                    assigned_agent="Delivery Health Analyst",
                    trigger_type="MANUAL",
                    definition={
                        "demo": True,
                        "external_writes": False,
                        "steps": ["collect", "assess", "human_review"],
                    },
                    status="ACTIVE",
                    created_by=MANIFEST,
                )
            )
        else:
            workflow.status = "ACTIVE"
        counts["workflows"] += 1

    for index, name in enumerate(
        [
            "Portfolio delivery evidence",
            "Release readiness library",
            "Meeting decision records",
            "Governance policy library",
        ]
    ):
        source = db.scalar(
            select(KnowledgeSource).where(
                KnowledgeSource.tenant_id == DEMO_TENANT, KnowledgeSource.name == name
            )
        )
        if source is None:
            db.add(
                KnowledgeSource(
                    tenant_id=DEMO_TENANT,
                    owner_id="ethan-brooks",
                    name=name,
                    source_type="DEMO_DOCUMENT",
                    location=f"demo://knowledge/{index}",
                    readiness_status="ready",
                    health_status="healthy",
                    last_synchronized_at=_dt(reference_date),
                )
            )
        counts["knowledge_sources"] += 1

    models = {}
    for _index, (key, name, status) in enumerate(
        [
            ("demo-default", "Approved Demo Default", "ACTIVE"),
            ("demo-low-cost", "Approved Demo Low Cost", "ACTIVE"),
            ("demo-evaluation", "Evaluation Only", "EVALUATION_ONLY"),
            ("demo-blocked", "Blocked Demo Model", "BLOCKED"),
            ("demo-retired", "Retired Demo Model", "RETIRED"),
        ]
    ):
        models[key] = _merge(
            db,
            GovernedModel,
            key,
            model_key=key,
            provider="demo",
            provider_model_id=f"fictional-{key}",
            display_name=name,
            model_family="fictional",
            capabilities=["text"],
            approved_use_cases=["DEMO"],
            prohibited_use_cases=["PRODUCTION"],
            allowed_data_classifications=["DEMO"],
            allowed_regions=["local"],
            status=status,
            context_limit=32000,
            configuration_version=1,
            effective_from=_dt(reference_date - timedelta(days=30)),
            created_by=MANIFEST,
            created_at=_dt(reference_date - timedelta(days=30)),
        )
        counts["governed_models"] += 1

    for index, (key, name) in enumerate(
        [
            ("ai-use", "Responsible AI use"),
            ("human-approval", "Human approval"),
            ("evidence", "Evidence grounding"),
            ("model-allowlist", "Model allowlist"),
            ("cost-control", "Cost control"),
        ]
    ):
        _merge(
            db,
            GovernancePolicy,
            key,
            policy_key=key,
            name=name,
            description="Versioned fictional demo governance policy.",
            category="AI_GOVERNANCE",
            version=1,
            status="ACTIVE",
            priority=10 + index,
            conditions={"classification": "DEMO"},
            effect={"decision": "ALLOW_WITH_CONTROLS"},
            reason_codes=["DEMO_POLICY"],
            effective_from=_dt(reference_date - timedelta(days=30)),
            review_date=_dt(reference_date + timedelta(days=90)),
            created_by=MANIFEST,
            approved_by="grace-wilson",
            created_at=_dt(reference_date - timedelta(days=30)),
            activated_at=_dt(reference_date - timedelta(days=29)),
        )
        counts["governance_policies"] += 1

    _merge(
        db,
        Budget,
        "demo-budget",
        scope_type="TENANT",
        scope_id=DEMO_TENANT,
        period="MONTHLY",
        soft_limit=Decimal("150.00"),
        hard_limit=Decimal("200.00"),
        currency="GBP",
        alert_thresholds=[50, 75, 90, 100],
        effective_from=_dt(reference_date.replace(day=1)),
        status="ACTIVE",
        created_by=MANIFEST,
    )
    counts["budgets"] += 1
    for index in range(14):
        _merge(
            db,
            UsageRecord,
            f"usage-{index}",
            trace_id=f"demo-trace-{index:03}",
            execution_id=stable_id("executions", str(index)),
            user_id="local-developer",
            programme_id=None,
            project_id=None,
            agent_id=None,
            model_id=models["demo-default"].id,
            provider="demo",
            input_tokens=1200 + index * 73,
            output_tokens=320 + index * 19,
            cached_input_tokens=200,
            reasoning_tokens=80,
            tool_calls=index % 4,
            latency_ms=600 + index * 37,
            status="COMPLETED",
            price_version=1,
            input_cost=Decimal("0.012") + Decimal(index) / 1000,
            output_cost=Decimal("0.008"),
            total_cost=Decimal("0.020") + Decimal(index) / 1000,
            currency="GBP",
            cost_estimated=False,
            started_at=_dt(reference_date - timedelta(days=13 - index), 9),
            completed_at=_dt(reference_date - timedelta(days=13 - index), 9),
        )
        counts["usage_records"] += 1
    for index, status in enumerate(["OPEN", "RESOLVED"]):
        _merge(
            db,
            AIIncident,
            f"incident-{index}",
            incident_type="MODEL_QUALITY",
            severity="LOW",
            status=status,
            owner_id="ethan-brooks",
            affected_services=["demo-runtime"],
            affected_tenant_refs=[DEMO_TENANT],
            trace_ids=[f"demo-trace-{index:03}"],
            impact_summary="Fictional low-severity demonstration incident.",
            mitigation="Human review completed."
            if status == "RESOLVED"
            else "Monitoring active.",
            corrective_actions=["review evidence"],
            timeline=[],
            created_by=MANIFEST,
            created_at=_dt(reference_date - timedelta(days=4 - index)),
            updated_at=_dt(reference_date),
        )
        counts["incidents"] += 1

    portfolio = _merge(
        db,
        DeliveryPortfolio,
        "enterprise-fy27",
        name="Enterprise Transformation Portfolio FY27",
        status="ACTIVE",
        owner_id="marcus-reed",
        created_by=MANIFEST,
        source_system="DEMO_SEED",
        record_metadata=_meta(
            reporting_period="FY27 Q1",
            base_currency="GBP",
            timezone="Europe/London",
            executive_sponsor="Eleanor Grant",
            portfolio_director="Marcus Reed",
            health="AMBER",
        ),
    )
    db.flush()
    counts["portfolios"] = 1
    programme_by_key = {}
    for key, name, status, health, owner, approved, actual, forecast in PROGRAMMES:
        programme_by_key[key] = _merge(
            db,
            DeliveryProgramme,
            key,
            portfolio_id=portfolio.id,
            name=name,
            status=status,
            owner_id=owner,
            created_by=MANIFEST,
            source_system="DEMO_SEED",
            record_metadata=_meta(
                manager=next(x[1] for x in PERSONAS if x[0] == owner),
                health=health,
                currency="GBP",
                approved_budget=str(approved),
                actual_spend=str(actual),
                forecast=str(forecast),
            ),
        )
        counts["programmes"] += 1
    db.flush()
    project_by_key, team_by_name = {}, {}
    for (
        key,
        programme_key,
        name,
        status,
        owner,
        team_name,
        approved,
        actual,
        forecast,
    ) in PROJECTS:
        project = _merge(
            db,
            DeliveryProject,
            key,
            programme_id=programme_by_key[programme_key].id,
            name=name,
            status=status,
            owner_id=owner,
            created_by=MANIFEST,
            source_system="DEMO_SEED",
            record_metadata=_meta(
                manager=next(x[1] for x in PERSONAS if x[0] == owner),
                strategic_theme={
                    "cx": "Customer experience",
                    "core": "Platform resilience",
                    "ops": "Operational efficiency",
                }[programme_key],
                confidence={"BLOCKED": 48, "AT_RISK": 67}.get(status, 88),
                currency="GBP",
                approved_budget=str(approved),
                actual_spend=str(actual),
                forecast=str(forecast),
            ),
        )
        project_by_key[key] = project
        counts["projects"] += 1
        if team_name not in team_by_name:
            team_by_name[team_name] = _merge(
                db,
                DeliveryTeam,
                team_name.lower(),
                project_id=project.id,
                name=team_name,
                status="ACTIVE",
                capacity=42,
                owner_id="nadia-rahman",
                created_by=MANIFEST,
                source_system="DEMO_SEED",
                record_metadata=_meta(),
            )
            counts["teams"] += 1
    db.flush()

    sprint_specs = [
        (
            "identity-14",
            "identity",
            "Sentinel",
            "Identity Sprint 14",
            "ACTIVE",
            -8,
            5,
            34,
            13,
            16,
            8,
        ),
        (
            "claims-22",
            "claims",
            "Phoenix",
            "Claims Sprint 22",
            "ACTIVE",
            -7,
            6,
            41,
            25,
            29,
            5,
        ),
        (
            "service-18",
            "service-desk",
            "FlowOps",
            "Service Automation Sprint 18",
            "ACTIVE",
            -6,
            7,
            36,
            31,
            33,
            1,
        ),
    ]
    for index, (
        key,
        project_key,
        team,
        name,
        status,
        start,
        end,
        committed,
        completed_original,
        completed,
        added,
    ) in enumerate(sprint_specs):
        sprint = _merge(
            db,
            DeliverySprint,
            key,
            project_id=project_by_key[project_key].id,
            team_id=team_by_name[team].id,
            name=name,
            status=status,
            goal="Deliver the next safe, evidenced increment",
            start_date=reference_date + timedelta(days=start),
            end_date=reference_date + timedelta(days=end),
            original_committed_points=committed,
            completed_original_points=completed_original,
            completed_points=completed,
            scope_added_points=added,
            scope_removed_points=0,
            owner_id="nadia-rahman",
            created_by=MANIFEST,
            source_system="DEMO_SEED",
            record_metadata=_meta(),
        )
        counts["sprints"] += 1
        for item_no in range(1, 7):
            critical = key == "identity-14" and item_no == 1
            _merge(
                db,
                DeliveryWorkItem,
                f"{key}-{item_no}",
                project_id=project_by_key[project_key].id,
                sprint_id=sprint.id,
                name="IDAM-241 — Complete Identity Token Exchange"
                if critical
                else f"{name} delivery item {item_no}",
                status="BLOCKED"
                if critical
                else ("COMPLETED" if item_no <= completed_original // 7 else "ACTIVE"),
                story_points=[3, 5, 8][item_no % 3],
                assignee_id="local-developer"
                if critical
                else ("aisha-khan" if item_no % 2 else "nadia-rahman"),
                goal_critical=critical or item_no == 2,
                blocked=critical,
                blocked_since=_dt(reference_date - timedelta(days=12))
                if critical
                else None,
                added_after_start=item_no == 6,
                created_by=MANIFEST,
                source_system="DEMO_SEED",
                record_metadata=_meta(
                    reference="IDAM-241"
                    if critical
                    else f"DEMO-{index + 1}{item_no:02}"
                ),
            )
            counts["work_items"] += 1
    # Six completed historical sprints make trend calculations meaningful.
    for index in range(6):
        project_key = ["claims", "identity", "service-desk"][index % 3]
        team = {"claims": "Phoenix", "identity": "Sentinel", "service-desk": "FlowOps"}[
            project_key
        ]
        _merge(
            db,
            DeliverySprint,
            f"history-{index}",
            project_id=project_by_key[project_key].id,
            team_id=team_by_name[team].id,
            name=f"Historical Sprint {index + 1}",
            status="COMPLETED",
            goal="Completed demo increment",
            start_date=reference_date - timedelta(days=28 + index * 14),
            end_date=reference_date - timedelta(days=15 + index * 14),
            original_committed_points=30 + index,
            completed_original_points=25 + index,
            completed_points=27 + index,
            scope_added_points=2,
            scope_removed_points=1,
            created_by=MANIFEST,
            source_system="DEMO_SEED",
            record_metadata=_meta(),
        )
        counts["sprints"] += 1
    db.flush()

    releases = {}
    release_specs = [
        ("atlas-32", "identity", "Atlas 3.2", "AT_RISK", 14, 52),
        ("claims-24", "claims", "Claims Portal 2.4", "PLANNED", 18, 72),
        ("data-16", "data", "Data Foundation 1.6", "READY", 25, 88),
        ("service-13", "service-desk", "Service Automation 1.3", "READY", 9, 94),
        ("finance-pilot", "finance", "Finance Workflow Pilot", "RELEASED", -8, 100),
    ]
    for key, project_key, name, status, offset, score in release_specs:
        releases[key] = _merge(
            db,
            DeliveryRelease,
            key,
            project_id=project_by_key[project_key].id,
            name=name,
            status=status,
            planned_date=reference_date + timedelta(days=offset),
            readiness_score=score,
            owner_id="liam-carter",
            created_by=MANIFEST,
            source_system="DEMO_SEED",
            record_metadata=_meta(
                environment="DEMO",
                recommendation="NO_GO" if key == "atlas-32" else "GO",
                fictional_reference=f"REL-{120 + len(releases)}",
            ),
        )
        counts["releases"] += 1
    db.flush()
    milestones = {}
    milestone_specs = [
        (
            "identity-integration",
            "identity",
            "Identity Integration Complete",
            "BLOCKED",
            -2,
            9,
            "atlas-32",
        ),
        (
            "atlas-ready",
            "identity",
            "Atlas 3.2 Production Readiness",
            "AT_RISK",
            12,
            18,
            "atlas-32",
        ),
        ("uat-entry", "claims", "UAT Entry", "AT_RISK", 4, 7, "claims-24"),
        ("uat-exit", "claims", "UAT Exit", "PLANNED", 13, 17, "claims-24"),
        (
            "consent",
            "data",
            "Customer Data Consent Design Approved",
            "COMPLETED",
            -12,
            -12,
            "data-16",
        ),
        (
            "performance",
            "cloud",
            "Platform Performance Baseline",
            "AT_RISK",
            8,
            13,
            None,
        ),
        (
            "service-wave",
            "service-desk",
            "Service Desk Automation Wave 1",
            "COMPLETED",
            -6,
            -6,
            "service-13",
        ),
        (
            "finance-pilot",
            "finance",
            "Finance Workflow Pilot Complete",
            "COMPLETED",
            -8,
            -7,
            "finance-pilot",
        ),
    ]
    for (
        key,
        project_key,
        name,
        status,
        planned,
        forecast,
        release_key,
    ) in milestone_specs:
        milestones[key] = _merge(
            db,
            DeliveryMilestone,
            key,
            project_id=project_by_key[project_key].id,
            release_id=releases[release_key].id if release_key else None,
            name=name,
            description="Fictional demonstration milestone",
            status=status,
            planned_date=reference_date + timedelta(days=planned),
            forecast_date=reference_date + timedelta(days=forecast),
            actual_date=reference_date + timedelta(days=forecast)
            if status == "COMPLETED"
            else None,
            critical=key in {"identity-integration", "atlas-ready", "uat-exit"},
            owner_id="liam-carter",
            created_by=MANIFEST,
            source_system="DEMO_SEED",
            record_metadata=_meta(),
        )
        counts["milestones"] += 1
    db.flush()

    dependency_specs = [
        (
            "DEP-017",
            "identity",
            "Identity API contract and token exchange",
            "BLOCKED",
            "CRITICAL",
            -12,
            "identity-integration",
            "WORK_ITEM",
            stable_id("delivery_work_items", "identity-14-1"),
        ),
        (
            "DEP-018",
            "claims",
            "UAT environment capacity",
            "AT_RISK",
            "HIGH",
            -1,
            None,
            "PROJECT",
            project_by_key["claims"].id,
        ),
        (
            "DEP-019",
            "data",
            "Consent architecture approval",
            "RESOLVED",
            "MEDIUM",
            -10,
            None,
            "PROJECT",
            project_by_key["data"].id,
        ),
    ]
    dependencies = {}
    for (
        ref,
        project_key,
        name,
        status,
        impact,
        due,
        _milestone_key,
        target_type,
        target_id,
    ) in dependency_specs:
        dep = _merge(
            db,
            DeliveryDependency,
            ref.lower(),
            reference=ref,
            project_id=project_by_key[project_key].id,
            name=name,
            description="Fictional internal dependency for connected demonstrations",
            dependency_type="CROSS_PROJECT",
            relationship_type="DELIVERS_TO",
            status=status,
            impact=impact,
            priority=impact,
            owner_id="local-developer" if ref == "DEP-017" else "oliver-hayes",
            provider_owner_id="oliver-hayes",
            consumer_owner_id="maya-chen",
            required_by_date=reference_date + timedelta(days=due),
            forecast_resolution_date=reference_date + timedelta(days=7),
            actual_resolution_date=reference_date - timedelta(days=8)
            if status == "RESOLVED"
            else None,
            resolved_at=_dt(reference_date - timedelta(days=8))
            if status == "RESOLVED"
            else None,
            blocked_since=_dt(reference_date - timedelta(days=12))
            if status == "BLOCKED"
            else None,
            critical_path=impact == "CRITICAL",
            external=False,
            created_by=MANIFEST,
            source_system="DEMO_SEED",
            record_metadata=_meta(),
        )
        dependencies[ref] = dep
        counts["dependencies"] += 1
        db.flush()
        db.merge(
            DeliveryDependencyEndpoint(
                dependency_id=dep.id,
                tenant_id=DEMO_TENANT,
                direction="SOURCE",
                entity_type="PROJECT",
                entity_id=project_by_key[project_key].id,
            )
        )
        db.merge(
            DeliveryDependencyEndpoint(
                dependency_id=dep.id,
                tenant_id=DEMO_TENANT,
                direction="TARGET",
                entity_type=target_type,
                entity_id=target_id,
            )
        )
    db.flush()

    raid_specs = [
        (
            "RISK-008",
            "identity",
            "Identity integration delay threatens Atlas 3.2",
            "RISK",
            "OPEN",
            "CRITICAL",
            "DEP-017",
        ),
        (
            "ISSUE-004",
            "claims",
            "UAT environment contention",
            "ISSUE",
            "OPEN",
            "HIGH",
            "DEP-018",
        ),
        (
            "RISK-011",
            "data",
            "Consent evidence is stale",
            "RISK",
            "MITIGATING",
            "MEDIUM",
            None,
        ),
        (
            "ASSUMP-003",
            "service-desk",
            "Automation adoption remains above forecast",
            "ASSUMPTION",
            "VALIDATING",
            "LOW",
            None,
        ),
        (
            "DEC-006",
            "identity",
            "Protect date pending 48-hour evidence review",
            "DECISION",
            "PENDING_APPROVAL",
            "HIGH",
            "DEP-017",
        ),
    ]
    for ref, project_key, name, item_type, status, impact, dep_ref in raid_specs:
        _merge(
            db,
            DeliveryRAIDItem,
            ref.lower(),
            project_id=project_by_key[project_key].id,
            programme_id=programme_by_key[
                next(x[1] for x in PROJECTS if x[0] == project_key)
            ].id,
            release_id=releases["atlas-32"].id if project_key == "identity" else None,
            milestone_id=milestones["identity-integration"].id
            if project_key == "identity"
            else None,
            dependency_id=dependencies[dep_ref].id if dep_ref else None,
            reference=ref,
            name=name,
            description="Fictional demonstration RAID record",
            item_type=item_type,
            status=status,
            priority=impact,
            impact=impact,
            probability="LIKELY" if impact in {"CRITICAL", "HIGH"} else "POSSIBLE",
            exposure_score={"CRITICAL": 25, "HIGH": 16, "MEDIUM": 9, "LOW": 4}[impact],
            exposure_band=impact,
            attention_score={"CRITICAL": 95, "HIGH": 76, "MEDIUM": 48, "LOW": 22}[
                impact
            ],
            due_date=reference_date + timedelta(days=-2 if impact == "CRITICAL" else 8),
            identified_at=_dt(reference_date - timedelta(days=20)),
            mitigation_plan="Review evidence, protect critical scope, and assign specialist capacity.",
            contingency_plan="Use a controlled delay if exit evidence remains incomplete.",
            critical_path=impact == "CRITICAL",
            owner_id="local-developer" if index < 3 else "nadia-rahman",
            created_by=MANIFEST,
            source_system="DEMO_SEED",
            record_metadata=_meta(),
        )
        counts["raid"] += 1
    db.flush()

    # Expand the core registers so charts, distributions, trends, and pagination
    # have enough persisted history to be visually useful.
    for index in range(6):
        project_key = ["claims", "identity", "service-desk"][index % 3]
        historical_sprint_id = stable_id("delivery_sprints", f"history-{index}")
        for item_no in range(1, 6):
            _merge(
                db,
                DeliveryWorkItem,
                f"history-{index}-item-{item_no}",
                project_id=project_by_key[project_key].id,
                sprint_id=historical_sprint_id,
                name=f"Historical delivery item {index + 1}.{item_no}",
                status="COMPLETED" if item_no < 5 else "CARRYOVER",
                story_points=[2, 3, 5, 8, 5][item_no - 1],
                assignee_id="aisha-khan",
                goal_critical=item_no == 2,
                blocked=False,
                added_after_start=item_no == 5,
                completed_at=_dt(reference_date - timedelta(days=15 + index * 14)),
                created_by=MANIFEST,
                source_system="DEMO_SEED",
                record_metadata=_meta(),
            )
            counts["work_items"] += 1
        _merge(
            db,
            DeliveryDefect,
            f"defect-{index}",
            project_id=project_by_key[project_key].id,
            sprint_id=historical_sprint_id,
            name=f"Historical quality defect {index + 1}",
            status="CLOSED" if index < 4 else "OPEN",
            severity=["LOW", "MEDIUM", "HIGH"][index % 3],
            escaped=index == 4,
            created_by=MANIFEST,
            source_system="DEMO_SEED",
            record_metadata=_meta(),
        )
        counts["defects"] += 1

    for index in range(9):
        provider_key = PROJECTS[index % len(PROJECTS)][0]
        consumer_key = PROJECTS[(index + 2) % len(PROJECTS)][0]
        ref = f"DEP-{20 + index:03}"
        status = ["OPEN", "AT_RISK", "ACKNOWLEDGED", "RESOLVED"][index % 4]
        dep = _merge(
            db,
            DeliveryDependency,
            ref.lower(),
            reference=ref,
            project_id=project_by_key[consumer_key].id,
            name=f"{project_by_key[provider_key].name} input for {project_by_key[consumer_key].name}",
            description="Connected fictional cross-project dependency.",
            dependency_type="CROSS_PROJECT",
            relationship_type="DEPENDS_ON",
            status=status,
            impact=["LOW", "MEDIUM", "HIGH"][index % 3],
            priority=["LOW", "MEDIUM", "HIGH"][index % 3],
            owner_id="nadia-rahman",
            provider_owner_id=project_by_key[provider_key].owner_id,
            consumer_owner_id=project_by_key[consumer_key].owner_id,
            required_by_date=reference_date + timedelta(days=index - 3),
            forecast_resolution_date=reference_date + timedelta(days=index + 2),
            actual_resolution_date=reference_date + timedelta(days=index - 2)
            if status == "RESOLVED"
            else None,
            resolved_at=_dt(reference_date + timedelta(days=index - 2))
            if status == "RESOLVED"
            else None,
            critical_path=index in {2, 6},
            created_by=MANIFEST,
            source_system="DEMO_SEED",
            record_metadata=_meta(),
        )
        db.flush()
        db.merge(
            DeliveryDependencyEndpoint(
                dependency_id=dep.id,
                tenant_id=DEMO_TENANT,
                direction="SOURCE",
                entity_type="PROJECT",
                entity_id=project_by_key[provider_key].id,
            )
        )
        db.merge(
            DeliveryDependencyEndpoint(
                dependency_id=dep.id,
                tenant_id=DEMO_TENANT,
                direction="TARGET",
                entity_type="PROJECT",
                entity_id=project_by_key[consumer_key].id,
            )
        )
        counts["dependencies"] += 1

    raid_types = ["RISK", "ASSUMPTION", "ISSUE", "DECISION"]
    for index in range(16):
        project_key = PROJECTS[index % len(PROJECTS)][0]
        item_type = raid_types[index % 4]
        impact = ["LOW", "MEDIUM", "HIGH", "CRITICAL"][index % 4]
        _merge(
            db,
            DeliveryRAIDItem,
            f"expanded-{index}",
            project_id=project_by_key[project_key].id,
            programme_id=programme_by_key[
                next(x[1] for x in PROJECTS if x[0] == project_key)
            ].id,
            reference=f"{item_type[:3]}-{100 + index}",
            name=f"{item_type.title()} for {project_by_key[project_key].name} checkpoint {index + 1}",
            description="Additional fictional record for register, distribution, and trend views.",
            item_type=item_type,
            status="CLOSED"
            if index in {3, 11}
            else ("PENDING_APPROVAL" if item_type == "DECISION" else "OPEN"),
            priority=impact,
            impact=impact,
            probability=["UNLIKELY", "POSSIBLE", "LIKELY"][index % 3],
            exposure_score=[4, 8, 16, 25][index % 4],
            exposure_band=impact,
            attention_score=[22, 45, 72, 91][index % 4],
            due_date=reference_date + timedelta(days=index - 6),
            identified_at=_dt(reference_date - timedelta(days=30 - index)),
            mitigation_plan="Owner reviewing evidence and next intervention.",
            contingency_plan="Escalate if deterministic thresholds are crossed.",
            critical_path=impact == "CRITICAL",
            owner_id="local-developer"
            if index < 4
            else project_by_key[project_key].owner_id,
            created_by=MANIFEST,
            source_system="DEMO_SEED",
            record_metadata=_meta(),
        )
        counts["raid"] += 1

    for index, project_key in enumerate(
        [
            "claims",
            "data",
            "omnichannel",
            "identity",
            "cloud",
            "observability",
            "service-desk",
        ]
    ):
        state = ["PLANNED", "AT_RISK", "COMPLETED"][index % 3]
        _merge(
            db,
            DeliveryMilestone,
            f"additional-{index}",
            project_id=project_by_key[project_key].id,
            name=f"{project_by_key[project_key].name} governance checkpoint",
            description="Additional checkpoint for portfolio trends.",
            status=state,
            planned_date=reference_date + timedelta(days=20 + index * 4),
            forecast_date=reference_date
            + timedelta(days=20 + index * 4 + (5 if index % 3 == 1 else 0)),
            actual_date=reference_date + timedelta(days=20 + index * 4)
            if state == "COMPLETED"
            else None,
            critical=index in {1, 3},
            owner_id="local-developer" if index < 3 else "nadia-rahman",
            created_by=MANIFEST,
            source_system="DEMO_SEED",
            record_metadata=_meta(),
        )
        counts["milestones"] += 1

    for key, project_key, name, offset, score in [
        ("cloud-wave-2", "cloud", "Cloud Migration Wave 2", 38, 66),
        ("omnichannel-20", "omnichannel", "Omnichannel Experience 2.0", 52, None),
    ]:
        _merge(
            db,
            DeliveryRelease,
            key,
            project_id=project_by_key[project_key].id,
            name=name,
            status="PLANNED",
            planned_date=reference_date + timedelta(days=offset),
            readiness_score=score,
            owner_id="liam-carter",
            created_by=MANIFEST,
            source_system="DEMO_SEED",
            record_metadata=_meta(environment="DEMO", recommendation="ASSESS"),
        )
        counts["releases"] += 1

    outcomes = [
        (
            "so-01",
            "Improve digital customer experience",
            "61",
            "30",
            "%",
            programme_by_key["cx"].id,
            "MEDIUM",
        ),
        (
            "so-02",
            "Strengthen platform resilience",
            "48",
            "99.95",
            "%",
            programme_by_key["core"].id,
            "LOW",
        ),
        (
            "so-03",
            "Reduce manual operational effort",
            "76",
            "40",
            "%",
            programme_by_key["ops"].id,
            "HIGH",
        ),
        (
            "so-04",
            "Improve delivery predictability",
            "69",
            "85",
            "%",
            programme_by_key["cx"].id,
            "MEDIUM",
        ),
        (
            "so-05",
            "Improve governance evidence coverage",
            "82",
            "95",
            "%",
            programme_by_key["core"].id,
            "MEDIUM",
        ),
    ]
    for key, name, current, target, unit, programme_id, confidence in outcomes:
        outcome = _merge(
            db,
            PortfolioStrategicOutcome,
            key,
            portfolio_id=portfolio.id,
            name=name,
            status="AT_RISK" if confidence in {"LOW", "MEDIUM"} else "ACTIVE",
            current_value=current,
            target_value=target,
            unit=unit,
            target_date=reference_date + timedelta(days=120),
            confidence={"LOW": 0.48, "MEDIUM": 0.69, "HIGH": 0.9}[confidence],
            owner_id="eleanor-grant",
            created_by=MANIFEST,
            source_system="DEMO_SEED",
            record_metadata=_meta(progress_source="Persisted delivery evidence"),
        )
        db.flush()
        db.merge(
            PortfolioOutcomeLink(
                id=stable_id("portfolio_outcome_links", key),
                tenant_id=DEMO_TENANT,
                outcome_id=outcome.id,
                entity_type="PROGRAMME",
                entity_id=programme_id,
                contribution=100,
            )
        )
        counts["outcomes"] += 1

    # Current programme/project snapshots reconcile exactly; portfolio history provides trends.
    for month in range(4):
        period = (reference_date.replace(day=1) - timedelta(days=month * 28)).replace(
            day=1
        )
        actual = Decimal("8150000") - Decimal(month * 1050000)
        _merge(
            db,
            PortfolioInvestmentSnapshot,
            f"portfolio-{period}",
            entity_type="PORTFOLIO",
            entity_id=portfolio.id,
            reporting_period=period,
            currency="GBP",
            approved_budget=Decimal("18400000"),
            actual_spend=max(actual, Decimal("0")),
            forecast=Decimal("19250000") - Decimal(month * 90000),
            committed=Decimal("14350000") - Decimal(month * 700000),
            contingency=Decimal("720000"),
            source_system="DEMO_FINANCE",
            source_timestamp=_dt(period + timedelta(days=24)),
        )
        counts["investment_snapshots"] += 1
    for programme_key, _, _, _, _, approved, actual, forecast in PROGRAMMES:
        _merge(
            db,
            PortfolioInvestmentSnapshot,
            f"programme-{programme_key}",
            entity_type="PROGRAMME",
            entity_id=programme_by_key[programme_key].id,
            reporting_period=reference_date.replace(day=1),
            currency="GBP",
            approved_budget=approved,
            actual_spend=actual,
            forecast=forecast,
            committed=actual + Decimal("900000"),
            contingency=Decimal("240000"),
            source_system="DEMO_FINANCE",
            source_timestamp=_dt(reference_date),
        )
        counts["investment_snapshots"] += 1
    for project_key, _, _, _, _, _, approved, actual, forecast in PROJECTS:
        _merge(
            db,
            PortfolioInvestmentSnapshot,
            f"project-{project_key}",
            entity_type="PROJECT",
            entity_id=project_by_key[project_key].id,
            reporting_period=reference_date.replace(day=1),
            currency="GBP",
            approved_budget=approved,
            actual_spend=actual,
            forecast=forecast,
            committed=actual + Decimal("250000"),
            contingency=Decimal("90000"),
            source_system="DEMO_FINANCE",
            source_timestamp=_dt(reference_date),
        )
        counts["investment_snapshots"] += 1

    evidence_targets = [
        (
            "DEPENDENCY",
            dependencies["DEP-017"].id,
            "Identity contract test evidence",
            -1,
        ),
        ("RELEASE", releases["atlas-32"].id, "Atlas 3.2 readiness checklist", -2),
        ("PROJECT", project_by_key["data"].id, "Customer data evidence pack", -31),
        (
            "SPRINT",
            stable_id("delivery_sprints", "identity-14"),
            "Identity Sprint 14 report",
            0,
        ),
    ]
    for index in range(28):
        entity_type, entity_id, title, age = evidence_targets[
            index % len(evidence_targets)
        ]
        _merge(
            db,
            DeliveryEvidence,
            f"evidence-{index}",
            entity_type=entity_type,
            entity_id=entity_id,
            dependency_id=dependencies["DEP-017"].id
            if entity_type == "DEPENDENCY"
            else None,
            source_type=[
                "SPRINT_REPORT",
                "TEST_SUMMARY",
                "MEETING_NOTES",
                "RELEASE_CHECKLIST",
            ][index % 4],
            source_system="DEMO_REPOSITORY",
            source_record_id=f"DEMO-EV-{index + 1:03}",
            title=f"{title} {index + 1}",
            summary="Fictional demonstration evidence; no external document is contacted.",
            source_url=f"https://demo.invalid/evidence/DEMO-EV-{index + 1:03}",
            captured_at=_dt(reference_date + timedelta(days=age - index % 3)),
            source_updated_at=_dt(reference_date + timedelta(days=age - index % 3)),
            content_hash=stable_id("hash", str(index)),
            created_at=_dt(reference_date),
        )
        counts["evidence"] += 1

    for index, (title, meeting_type, project_key) in enumerate(
        [
            ("Atlas 3.2 Release Readiness Review", "RELEASE_READINESS", "identity"),
            ("Executive Portfolio Review", "EXECUTIVE_REVIEW", "identity"),
            ("Customer Experience Delivery Review", "PROGRAMME_REVIEW", "claims"),
            ("Identity Architecture Dependency Workshop", "WORKSHOP", "identity"),
            ("Operations Automation Sprint Review", "SPRINT_REVIEW", "service-desk"),
            ("FY27 Q1 Financial Review", "FINANCIAL_REVIEW", "finance"),
            ("Portfolio RAID Review", "RAID_REVIEW", "identity"),
            ("Claims Daily Scrum", "DAILY_SCRUM", "claims"),
        ]
    ):
        meeting = _merge(
            db,
            Meeting,
            f"meeting-{index}",
            title=title,
            meeting_type=meeting_type,
            status="REVIEWED" if index < 5 else "SCHEDULED",
            description="Fictional demonstration meeting",
            organizer_id="nadia-rahman",
            scheduled_start=_dt(reference_date + timedelta(days=index - 4), 10),
            scheduled_end=_dt(reference_date + timedelta(days=index - 4), 11),
            timezone="Europe/London",
            project_id=project_by_key[project_key].id,
            release_id=releases["atlas-32"].id if project_key == "identity" else None,
            source_system="DEMO_SEED",
            created_by=MANIFEST,
            meeting_metadata=_meta(),
        )
        db.flush()
        db.merge(
            MeetingParticipant(
                id=stable_id("meeting_participants", f"{index}-nadia"),
                tenant_id=DEMO_TENANT,
                meeting_id=meeting.id,
                user_id="nadia-rahman",
                display_name="Nadia Rahman",
                role="Delivery Lead",
                attendance_status="ACCEPTED",
            )
        )
        counts["meetings"] += 1

    for index, (name, connector, status) in enumerate(
        [
            ("Jira Cloud Demo Adapter", "jira", "connected"),
            ("Microsoft Teams", "teams", "not_configured"),
            ("Outlook Calendar", "outlook", "not_configured"),
            ("ServiceNow", "servicenow", "draft"),
            ("Azure DevOps", "azure_devops", "disabled"),
            ("Financial ERP", "erp", "planned"),
        ]
    ):
        _merge(
            db,
            IntegrationConnection,
            f"integration-{index}",
            connector_type=connector,
            name=f"demo-{connector}",
            display_name=name,
            description="Fictional safe demo configuration",
            auth_type="none",
            status=status,
            health_status="healthy" if status == "connected" else "not_configured",
            base_url="https://demo.invalid",
            secret_ref=None,
            configuration={},
            safe_metadata={"data_classification": "DEMO", "seed_manifest": MANIFEST},
            created_by=MANIFEST,
            enabled=status == "connected",
        )
        counts["integrations"] += 1

    _merge(
        db,
        DeliveryRecommendation,
        "critical-intervention",
        entity_type="DEPENDENCY",
        entity_id=dependencies["DEP-017"].id,
        dependency_id=dependencies["DEP-017"].id,
        title="Protect Atlas 3.2 critical scope",
        explanation="Add specialist capacity and require tested token-exchange evidence before release approval.",
        status="NEW",
        priority="CRITICAL",
        confidence=0.91,
    )
    counts["recommendations"] += 1
    action_specs = [
        (
            "escalate-dep",
            "Escalate Identity API dependency",
            "PENDING_APPROVAL",
            "CRITICAL",
        ),
        ("uat-support", "Request additional UAT support", "PROPOSED", "HIGH"),
        (
            "performance-evidence",
            "Request performance-test evidence",
            "DRAFT",
            "MEDIUM",
        ),
        (
            "release-condition",
            "Propose Atlas 3.2 release condition",
            "PENDING_APPROVAL",
            "HIGH",
        ),
        (
            "stakeholder-comms",
            "Draft controlled-delay communication",
            "APPROVED",
            "MEDIUM",
        ),
        (
            "raid-mitigation",
            "Create specialist-capacity mitigation",
            "EXECUTED",
            "HIGH",
        ),
        (
            "unsafe-scope",
            "Reject automatic critical-scope removal",
            "REJECTED",
            "CRITICAL",
        ),
        (
            "verify-evidence",
            "Verify updated token-exchange evidence",
            "VERIFIED",
            "MEDIUM",
        ),
    ]
    for index, (key, title, status, risk) in enumerate(action_specs):
        action = _merge(
            db,
            ProposedAction,
            key,
            dependency_id=dependencies["DEP-017"].id if index in {0, 2, 3, 7} else None,
            raid_id=stable_id("delivery_raid_items", "risk-008")
            if index in {0, 5}
            else None,
            sprint_id=stable_id("delivery_sprints", "identity-14"),
            work_item_id=stable_id("delivery_work_items", "identity-14-1"),
            action_type="CREATE_INTERNAL_RECORD",
            title=title,
            description="Fictional governed internal demonstration action.",
            content=title,
            origin="DEMO_SEED",
            requester_id="nadia-rahman",
            target_entity_type="DEPENDENCY",
            target_entity_id=dependencies["DEP-017"].id,
            target_system="INTERNAL",
            payload={"demo": True, "reference": "DEP-017"},
            original_payload={"demo": True, "reference": "DEP-017"},
            owner_id="local-developer" if index < 5 else "aisha-khan",
            due_date=reference_date + timedelta(days=index - 2),
            status=status,
            risk_classification="CONTROLLED",
            risk_level=risk,
            approval_required=status not in {"DRAFT", "PROPOSED"},
            required_approval_count=1,
            expires_at=_dt(reference_date + timedelta(days=30)),
            idempotency_key=f"demo-action-{key}",
            submitted_at=_dt(reference_date - timedelta(days=2))
            if status not in {"DRAFT", "PROPOSED"}
            else None,
            approved_at=_dt(reference_date - timedelta(days=1))
            if status in {"APPROVED", "EXECUTED", "VERIFIED"}
            else None,
            executed_at=_dt(reference_date)
            if status in {"EXECUTED", "VERIFIED"}
            else None,
            verified_at=_dt(reference_date) if status == "VERIFIED" else None,
            created_by=MANIFEST,
            created_at=_dt(reference_date - timedelta(days=5)),
            updated_at=_dt(reference_date),
        )
        counts["actions"] += 1
        if status == "PENDING_APPROVAL":
            db.flush()
            db.merge(
                ApprovalRequest(
                    id=stable_id("approval_requests", key),
                    tenant_id=DEMO_TENANT,
                    proposed_action_id=action.id,
                    action_version=1,
                    tool_name="internal.demo.action",
                    tool_version="1.0",
                    requester_id="nadia-rahman",
                    assigned_approver_id="local-developer"
                    if index == 0
                    else "grace-wilson",
                    required_approver_role="APPROVER",
                    required_approval_count=1,
                    separation_of_duties=True,
                    risk_level=risk,
                    environment="development",
                    safe_action_summary={"title": title, "demo": True},
                    input_fingerprint=stable_id("fingerprint", key).replace("-", ""),
                    status="PENDING",
                    created_at=_dt(reference_date - timedelta(days=2)),
                    expires_at=_dt(reference_date + timedelta(days=5)),
                    resume_token_hash=stable_id("resume", key).replace("-", ""),
                    audit_metadata={
                        "seed_manifest": MANIFEST,
                        "data_classification": "DEMO",
                    },
                )
            )
            counts["approvals"] += 1
    return dict(sorted(counts.items()))


def validate_demo(db: Session) -> dict[str, int]:
    portfolio = db.scalar(
        select(DeliveryPortfolio).where(DeliveryPortfolio.tenant_id == DEMO_TENANT)
    )
    if (
        portfolio is None
        or (portfolio.record_metadata or {}).get("data_classification") != "DEMO"
    ):
        raise DemoSeedError("Demo tenant classification is missing")
    counts = {
        model.__tablename__: db.scalar(
            select(func.count())
            .select_from(model)
            .where(model.tenant_id == DEMO_TENANT)
        )
        for model in (
            DeliveryPortfolio,
            DeliveryProgramme,
            DeliveryProject,
            DeliveryTeam,
            DeliverySprint,
            DeliveryWorkItem,
            DeliveryRelease,
            DeliveryMilestone,
            DeliveryDependency,
            DeliveryRAIDItem,
            DeliveryEvidence,
            PortfolioStrategicOutcome,
            PortfolioInvestmentSnapshot,
            Meeting,
        )
    }
    if counts["delivery_programmes"] != 3 or counts["delivery_projects"] != 8:
        raise DemoSeedError("Portfolio hierarchy does not match the seed manifest")
    latest = list(
        db.scalars(
            select(PortfolioInvestmentSnapshot).where(
                PortfolioInvestmentSnapshot.tenant_id == DEMO_TENANT,
                PortfolioInvestmentSnapshot.entity_type == "PROGRAMME",
                PortfolioInvestmentSnapshot.reporting_period
                == max(
                    db.scalars(
                        select(PortfolioInvestmentSnapshot.reporting_period).where(
                            PortfolioInvestmentSnapshot.tenant_id == DEMO_TENANT
                        )
                    )
                ),
            )
        )
    )
    if (
        sum((x.approved_budget or 0 for x in latest), Decimal()) != Decimal("18400000")
        or sum((x.actual_spend or 0 for x in latest), Decimal()) != Decimal("8150000")
        or sum((x.forecast or 0 for x in latest), Decimal()) != Decimal("19250000")
    ):
        raise DemoSeedError("Programme financial snapshots do not reconcile")
    endpoint_count = db.scalar(
        select(func.count())
        .select_from(DeliveryDependencyEndpoint)
        .where(DeliveryDependencyEndpoint.tenant_id == DEMO_TENANT)
    )
    if endpoint_count != counts["delivery_dependencies"] * 2:
        raise DemoSeedError("Dependency endpoints are incomplete")
    return counts


def reset_demo(db: Session, tenant_id: str, confirmation: str) -> None:
    assert_safe_environment(tenant_id)
    if confirmation != tenant_id:
        raise DemoSeedError("--confirm-tenant must exactly match the demo tenant")
    portfolio = db.scalar(
        select(DeliveryPortfolio).where(DeliveryPortfolio.tenant_id == tenant_id)
    )
    if (
        portfolio is not None
        and (portfolio.record_metadata or {}).get("data_classification") != "DEMO"
    ):
        raise DemoSeedError("Refusing to reset a tenant not classified as DEMO")
    for table in reversed(Base.metadata.sorted_tables):
        if "tenant_id" in table.c:
            db.execute(delete(table).where(table.c.tenant_id == tenant_id))
    db.commit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed connected fictional Axiom demonstration data"
    )
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--scenario", choices=[SCENARIO], default=SCENARIO)
    parser.add_argument(
        "--reference-date", type=date.fromisoformat, default=date(2026, 10, 6)
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--reset-demo-tenant", action="store_true")
    parser.add_argument("--confirm-tenant")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    assert_safe_environment(args.tenant_id)
    with SessionLocal() as db:
        assert_safe_database(db)
        if args.reset_demo_tenant:
            reset_demo(db, args.tenant_id, args.confirm_tenant or "")
            print(f"Reset complete for exact demo tenant {args.tenant_id}")
            return
        if args.validate:
            print("Validated:", validate_demo(db))
            return
        counts = seed_demo(db, args.reference_date)
        validation = validate_demo(db)
        if args.dry_run:
            db.rollback()
            print("Dry run (rolled back):", counts)
        else:
            db.commit()
            print("Seeded:", counts)
        print("Validated relationships:", validation)


if __name__ == "__main__":
    main()
