from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from time import perf_counter

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.delivery import (
    DeliveryDependency,
    DeliveryPortfolio,
    DeliveryProgramme,
    DeliveryProject,
    DeliveryRelease,
    DeliverySprint,
    DeliveryTeam,
    DeliveryWorkItem,
)
from app.delivery.dependency_intelligence import (
    DependencyGraph,
    GraphEdge,
    dependency_health,
    dependency_priority,
    impact_result,
    validate_transition,
)
from app.delivery.dependency_repository import DependencyRepository
from app.main import app


def hierarchy(db, tenant: str = "tenant-a"):
    portfolio = DeliveryPortfolio(
        tenant_id=tenant, name="Synthetic Portfolio", status="ACTIVE"
    )
    db.add(portfolio)
    db.flush()
    programme = DeliveryProgramme(
        tenant_id=tenant,
        name="Synthetic Programme",
        portfolio_id=portfolio.id,
        status="ACTIVE",
    )
    db.add(programme)
    db.flush()
    project = DeliveryProject(
        tenant_id=tenant,
        name="Synthetic Project",
        programme_id=programme.id,
        status="ACTIVE",
    )
    db.add(project)
    db.flush()
    team = DeliveryTeam(
        tenant_id=tenant, name="Team Phoenix", project_id=project.id, status="ACTIVE"
    )
    db.add(team)
    db.flush()
    sprint = DeliverySprint(
        tenant_id=tenant,
        name="Sprint 24",
        project_id=project.id,
        team_id=team.id,
        goal="Ship synthetic payments",
        status="ACTIVE",
        start_date=date.today() - timedelta(days=3),
        end_date=date.today() + timedelta(days=7),
    )
    release = DeliveryRelease(
        tenant_id=tenant,
        name="Release 4",
        project_id=project.id,
        status="PLANNED",
        planned_date=date.today() + timedelta(days=14),
    )
    work = DeliveryWorkItem(
        tenant_id=tenant,
        name="Mobile App",
        project_id=project.id,
        sprint_id=sprint.id,
        status="IN_PROGRESS",
        goal_critical=True,
    )
    db.add_all((sprint, release, work))
    db.flush()
    return project, team, sprint, release, work


def values(project_id: str, reference: str, name: str, **overrides):
    result = {
        "reference": reference,
        "name": name,
        "description": f"Synthetic {name} dependency",
        "project_id": project_id,
        "dependency_type": "TECHNICAL",
        "relationship_type": "DEPENDS_ON",
        "status": "IN_PROGRESS",
        "impact": "HIGH",
        "owner_id": "owner-1",
        "provider_owner_id": "provider-1",
        "required_by_date": date.today() + timedelta(days=5),
        "forecast_resolution_date": date.today() + timedelta(days=8),
        "committed_resolution_date": date.today() + timedelta(days=4),
        "acknowledged_at": datetime.now(UTC),
        "last_reviewed_at": datetime.now(UTC),
        "critical_path": True,
        "external": True,
        "source_system": "MANUAL",
        "record_metadata": {},
    }
    result.update(overrides)
    return result


def create_chain(db, tenant: str = "tenant-a"):
    project, team, sprint, release, work = hierarchy(db, tenant)
    repo = DependencyRepository(db, tenant, "owner-1")
    specs = [
        (
            "D-016",
            "Identity Service",
            ("SYSTEM", "identity-service"),
            ("SYSTEM", "payment-api"),
        ),
        ("D-017", "Payment API", ("SYSTEM", "payment-api"), ("SYSTEM", "customer-api")),
        (
            "D-018",
            "Customer API delivery",
            ("SYSTEM", "customer-api"),
            ("WORK_ITEM", work.id),
        ),
        ("D-019", "Mobile App sprint", ("WORK_ITEM", work.id), ("SPRINT", sprint.id)),
        ("D-020", "Sprint release", ("SPRINT", sprint.id), ("RELEASE", release.id)),
    ]
    dependencies = [
        repo.create(
            values(project.id, reference, name), source, target, f"trace-{reference}"
        )
        for reference, name, source, target in specs
    ]
    db.commit()
    return repo, dependencies, (project, team, sprint, release, work)


def test_graph_cycle_paths_topological_impact_and_bottlenecks():
    edges = [
        GraphEdge(
            "d1", "SYSTEM:identity", "SYSTEM:payment", status="AT_RISK", critical=True
        ),
        GraphEdge(
            "d2", "SYSTEM:payment", "SYSTEM:customer", status="BLOCKED", critical=True
        ),
        GraphEdge(
            "d3",
            "SYSTEM:customer",
            "SPRINT:s24",
            required_by=date.today(),
            forecast_resolution=date.today() + timedelta(days=2),
        ),
        GraphEdge("d4", "ENVIRONMENT:sit", "SPRINT:s24", status="BLOCKED"),
        GraphEdge("d5", "SPRINT:s24", "RELEASE:r4", critical=True),
    ]
    graph = DependencyGraph(edges)
    assert graph.cycle_path() == []
    cycle = graph.cycle_path(GraphEdge("cycle", "RELEASE:r4", "SYSTEM:identity"))
    assert cycle[0] == cycle[-1]
    assert {"SYSTEM:identity", "RELEASE:r4"} <= set(cycle)
    assert graph.topological_order().index(
        "SYSTEM:identity"
    ) < graph.topological_order().index("RELEASE:r4")
    assert [
        edge.dependency_id for edge in graph.paths("SYSTEM:identity", "RELEASE:r4")[0]
    ] == ["d1", "d2", "d3", "d5"]
    critical = graph.critical_paths()[0]
    assert critical["classification"] == "POTENTIAL_CRITICAL_PATH"
    impact = impact_result(graph, edges[1], slip_days=5)
    assert impact["affectedSprints"] == ["s24"]
    assert impact["affectedReleases"] == ["r4"]
    assert impact["readOnly"] is True
    assert graph.bottlenecks()[0]["node"] == "SPRINT:s24"


def test_health_priority_missing_data_and_lifecycle_are_explainable():
    incomplete = DeliveryDependency(
        tenant_id="tenant-a",
        reference="D-001",
        project_id="project",
        name="Incomplete",
        description="Missing controls",
        dependency_type="TECHNICAL",
        status="IDENTIFIED",
    )
    assert (
        dependency_health(incomplete, evidence_count=0, downstream_count=0)["status"]
        == "UNKNOWN"
    )
    dependency = DeliveryDependency(
        tenant_id="tenant-a",
        reference="D-002",
        project_id="project",
        name="Late dependency",
        description="Late",
        dependency_type="TECHNICAL",
        status="BLOCKED",
        owner_id="owner",
        provider_owner_id="provider",
        required_by_date=date.today(),
        forecast_resolution_date=date.today() + timedelta(days=5),
        identified_at=datetime.now(UTC) - timedelta(days=40),
        critical_path=True,
        external=True,
    )
    health = dependency_health(dependency, evidence_count=0, downstream_count=4)
    priority = dependency_priority(
        dependency,
        downstream_nodes=["SPRINT:s24", "RELEASE:r4", "TEAM:phoenix"],
        evidence_count=0,
    )
    assert health["status"] == "RED"
    assert priority["band"] == "CRITICAL"
    assert {factor["factor"] for factor in priority["triggeredFactors"]} >= {
        "Critical-path dependency",
        "Currently blocked",
        "Release impact",
    }
    validate_transition("IN_PROGRESS", "BLOCKED")
    with pytest.raises(ValueError, match="Escalation requires"):
        validate_transition("BLOCKED", "ESCALATED")
    with pytest.raises(ValueError, match="Invalid"):
        validate_transition("CLOSED", "IN_PROGRESS")


def test_repository_is_tenant_scoped_rejects_duplicates_cycles_and_concurrency(
    db_session,
):
    repo, dependencies, (_, _, _, release, _) = create_chain(db_session)
    assert repo.get(dependencies[2].id).reference == "D-018"
    assert len(repo.graph()[0].edges) == 5
    with pytest.raises(ValueError, match="Duplicate"):
        repo.create(
            values(dependencies[0].project_id, "D-099", "Duplicate"),
            ("SYSTEM", "identity-service"),
            ("SYSTEM", "payment-api"),
            "duplicate",
        )
    with pytest.raises(ValueError, match="cycle"):
        repo.create(
            values(dependencies[0].project_id, "D-098", "Cycle"),
            ("RELEASE", release.id),
            ("SYSTEM", "identity-service"),
            "cycle",
        )
    with pytest.raises(ValueError, match="modified"):
        repo.update(dependencies[0], {"impact": "LOW"}, version=99, trace_id="conflict")
    assert (
        DependencyRepository(db_session, "tenant-b", "other").get(dependencies[0].id)
        is None
    )


def test_authenticated_api_graph_scenario_proposal_and_negative_tenant(db_session):
    repo, dependencies, _ = create_chain(db_session)
    target = dependencies[2]
    identity = {"sub": "owner-1", "custom:tenant_id": "tenant-a", "permissions": []}
    app.dependency_overrides[get_current_user] = lambda: identity
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as client:
            listing = client.get("/api/dependencies")
            assert listing.status_code == 200
            assert listing.json()["total"] == 5
            assert (
                client.get("/api/dependencies/summary").json()["criticalDependencies"]
                >= 1
            )
            graph = client.get("/api/dependencies/graph").json()
            assert graph["edgeCount"] == 5
            impact = client.post(
                "/api/dependencies/graph/impact",
                json={"dependency_id": target.id, "slip_days": 5},
            ).json()
            assert impact["affectedSprints"]
            scenario = client.post(
                "/api/dependencies/graph/scenarios",
                json={"dependency_id": target.id, "slip_days": 5, "save": True},
            ).json()
            assert scenario["saved"] is True
            assert scenario["authoritativeRecordsChanged"] is False
            proposal = client.post(
                f"/api/dependencies/{target.id}/proposals",
                json={
                    "action_type": "DRAFT_ESCALATION",
                    "content": "Draft provider escalation for human review.",
                    "status": "PROPOSED",
                },
            ).json()
            assert proposal["externalWrites"] is False
            detail = client.get(f"/api/dependencies/{target.id}").json()
            assert detail["scenarios"] and detail["proposals"]
            copilot = client.post(
                "/api/dependencies/copilot",
                json={
                    "question": "What if D-018 slips five days?",
                    "dependency_id": target.id,
                    "slip_days": 5,
                },
            ).json()
            assert copilot["responseType"] == "DEPENDENCY_INTELLIGENCE"
            assert copilot["externalWrites"] is False
            identity["custom:tenant_id"] = "tenant-b"
            assert client.get(f"/api/dependencies/{target.id}").status_code == 404
            assert client.get("/api/dependencies/graph").json()["edgeCount"] == 0
    finally:
        app.dependency_overrides.clear()
    assert repo.get(target.id) is not None


def test_graph_performance_at_required_representative_sizes():
    for node_count, edge_count in ((1_000, 5_000), (5_000, 20_000)):
        edges = [
            GraphEdge(
                f"d-{index}",
                f"SYSTEM:n{index % (node_count - 1)}",
                f"SYSTEM:n{min((index % (node_count - 1)) + 1, node_count - 1)}",
            )
            for index in range(edge_count)
        ]
        started = perf_counter()
        graph = DependencyGraph(edges)
        assert graph.cycle_path() == []
        assert len(graph.topological_order()) == node_count
        assert perf_counter() - started < 5
