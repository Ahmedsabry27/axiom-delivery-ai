from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.delivery.portfolio_service import PortfolioIntelligenceService

router = APIRouter(prefix="/api", tags=["Portfolio Intelligence"])


def _permissions(user: dict) -> tuple[set[str], bool]:
    raw = user.get("scope", "")
    permissions = set(raw.split()) | set(user.get("permissions") or [])
    groups = {str(group).lower() for group in user.get("cognito:groups", []) or []}
    admin = (
        bool(groups & {"admin", "administrators", "platform-admin"})
        or "tools.admin" in permissions
    )
    if permissions and not admin and "portfolio.read" not in permissions:
        raise HTTPException(403, "portfolio.read permission is required")
    financial = admin or not permissions or "portfolio.financials.read" in permissions
    return permissions, financial


def _workspace(user: dict, db: Session) -> dict:
    _, financial = _permissions(user)
    return PortfolioIntelligenceService(
        db, user["custom:tenant_id"], user["sub"]
    ).workspace(financial_access=financial)


def _one(items: list[dict], entity_id: str) -> dict:
    item = next((row for row in items if row["id"] == entity_id), None)
    if item is None:
        raise HTTPException(404, "Entity not found or inaccessible")
    return item


@router.get("/portfolios")
def list_portfolios(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    data = _workspace(user, db)
    return {
        "items": data["portfolios"],
        "health": data["health"],
        "generatedAt": data["generatedAt"],
    }


@router.get("/portfolios/{portfolio_id}")
def get_portfolio(
    portfolio_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = _workspace(user, db)
    return {**_one(data["portfolios"], portfolio_id), "health": data["health"]}


@router.get("/portfolios/{portfolio_id}/{section}")
def get_portfolio_section(
    portfolio_id: str,
    section: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = _workspace(user, db)
    _one(data["portfolios"], portfolio_id)
    allowed = {
        "programmes",
        "projects",
        "outcomes",
        "milestones",
        "insights",
        "attention",
    }
    if section == "investments":
        return data["investment"] | {"items": data["programmes"]}
    if section not in allowed:
        raise HTTPException(404, "Portfolio section not found")
    items = data[section]
    if section in {"programmes", "outcomes"}:
        items = [row for row in items if row.get("portfolioId") == portfolio_id]
    return {"items": items, "generatedAt": data["generatedAt"]}


@router.get("/programmes")
def list_programmes(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    return {"items": _workspace(user, db)["programmes"]}


@router.get("/programmes/{programme_id}")
def get_programme(
    programme_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = _workspace(user, db)
    programme = _one(data["programmes"], programme_id)
    return {
        **programme,
        "projects": [
            row for row in data["projects"] if row["programmeId"] == programme_id
        ],
    }


@router.get("/projects")
def list_projects(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    return {"items": _workspace(user, db)["projects"]}


@router.get("/projects/{project_id}")
def get_project(
    project_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = _workspace(user, db)
    project = _one(data["projects"], project_id)
    return {
        **project,
        "milestones": [
            row for row in data["milestones"] if row["projectId"] == project_id
        ],
    }
