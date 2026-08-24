from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
)
from app.services.conversation_service import conversation_service

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


# --------------------------------------------------
# Create Conversation
# --------------------------------------------------
@router.post("", response_model=ConversationResponse)
def create_conversation(
    request: ConversationCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return conversation_service.create_conversation(
        db=db,
        user_id=user["sub"],
        title=request.title,
        tenant_id=user.get("custom:tenant_id", "default"),
    )


# --------------------------------------------------
# Get All Conversations
# --------------------------------------------------
@router.get("", response_model=list[ConversationResponse])
def get_conversations(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return conversation_service.get_conversations(
        db=db,
        user_id=user["sub"],
    )


# --------------------------------------------------
# Get Conversation
# --------------------------------------------------
@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def get_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    conversation = conversation_service.get_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=user["sub"],
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    return conversation


# --------------------------------------------------
# Update Conversation Title
# --------------------------------------------------
@router.patch(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def update_conversation(
    conversation_id: UUID,
    request: ConversationUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    conversation = conversation_service.update_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=user["sub"],
        title=request.title,
        is_pinned=request.is_pinned,
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    return conversation


# --------------------------------------------------
# Get Conversation Messages
# --------------------------------------------------
@router.get("/{conversation_id}/messages")
def get_messages(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    messages = conversation_service.get_messages(
        db=db,
        conversation_id=conversation_id,
        user_id=user["sub"],
    )

    return messages


# --------------------------------------------------
# Delete Conversation
# --------------------------------------------------
@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    deleted = conversation_service.delete_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=user["sub"],
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    return {
        "message": "Conversation deleted",
    }
