from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.routers.dashboard import agent_status, recent_executions
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db

router = APIRouter(prefix="/api", tags=["Operations"])


@router.get("/executions/recent")
def operations_recent_executions(
    db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    return recent_executions(db, user)


@router.get("/agents/status")
def operations_agent_status(user: dict = Depends(get_current_user)):
    return agent_status(user)
