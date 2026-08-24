from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.models.runtime_execution import RuntimeExecution

router = APIRouter(prefix="/api/audit", tags=["Audit"])


@router.get("/runtime-executions")
def list_runtime_executions(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    records = (
        db.query(RuntimeExecution)
        .filter(RuntimeExecution.user_id == user["sub"])
        .order_by(RuntimeExecution.started_at.desc())
        .all()
    )
    return [
        {
            "id": str(record.id),
            "time": record.started_at,
            "user": record.user_id,
            "workflow_id": str(record.workflow_id),
            "agent": record.agent,
            "status": record.status,
            "duration_ms": record.duration_ms,
        }
        for record in records
    ]
