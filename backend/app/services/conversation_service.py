from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.conversation_repository import (
    conversation_repository,
)
from app.repositories.message_repository import (
    message_repository,
)


class ConversationService:
    # --------------------------------------------------
    # Conversation CRUD
    # --------------------------------------------------

    def create_conversation(
        self,
        db: Session,
        user_id: str,
        title: str = "New Conversation",
        tenant_id: str = "default",
    ):
        return conversation_repository.create(
            db=db,
            user_id=user_id,
            title=title,
            tenant_id=tenant_id,
        )

    def get_conversations(
        self,
        db: Session,
        user_id: str,
        tenant_id: str | None = None,
    ):
        return conversation_repository.get_all(
            db=db,
            user_id=user_id,
            tenant_id=tenant_id,
        )

    def get_conversation(
        self,
        db: Session,
        conversation_id: UUID,
        user_id: str,
        tenant_id: str | None = None,
    ):
        return conversation_repository.get_by_id(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )

    # --------------------------------------------------
    # Update Conversation
    # --------------------------------------------------

    def update_conversation_title(
        self,
        db: Session,
        conversation_id: UUID,
        user_id: str,
        title: str,
    ):
        conversation = self.get_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
        )

        if conversation is None:
            return None

        return conversation_repository.update_title(
            db=db,
            conversation=conversation,
            title=title,
        )

    def update_conversation(
        self,
        db: Session,
        conversation_id: UUID,
        user_id: str,
        tenant_id: str | None = None,
        *,
        title: str | None = None,
        is_pinned: bool | None = None,
        is_archived: bool | None = None,
        context_summary: dict | None = None,
    ):
        conversation = self.get_conversation(
            db=db, conversation_id=conversation_id, user_id=user_id, tenant_id=tenant_id
        )
        if conversation is None:
            return None
        return conversation_repository.update(
            db,
            conversation,
            title=title,
            is_pinned=is_pinned,
            is_archived=is_archived,
            context_summary=context_summary,
        )

    # --------------------------------------------------
    # Delete Conversation
    # --------------------------------------------------

    def delete_conversation(
        self,
        db: Session,
        conversation_id: UUID,
        user_id: str,
        tenant_id: str | None = None,
    ):
        conversation = self.get_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )

        if conversation is None:
            return None

        return conversation_repository.delete(
            db=db,
            conversation=conversation,
        )

    # --------------------------------------------------
    # Conversation Activity
    # --------------------------------------------------

    def touch_conversation(
        self,
        db: Session,
        conversation_id: UUID,
        user_id: str,
    ):
        conversation = self.get_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
        )

        if conversation is None:
            return None

        return conversation_repository.touch(
            db=db,
            conversation=conversation,
        )

    # --------------------------------------------------
    # Messages
    # --------------------------------------------------

    def save_user_message(
        self,
        db: Session,
        conversation_id: UUID,
        content: str,
    ):
        return message_repository.create(
            db=db,
            conversation_id=conversation_id,
            role="user",
            content=content,
        )

    def save_assistant_message(
        self,
        db: Session,
        conversation_id: UUID,
        content: str,
        response_id: str | None,
    ):
        return message_repository.create(
            db=db,
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            response_id=response_id,
        )

    def get_messages(
        self,
        db: Session,
        conversation_id: UUID,
        user_id: str,
        tenant_id: str | None = None,
    ):
        """
        Returns all messages for a conversation after verifying
        that the conversation belongs to the authenticated user.
        """

        conversation = self.get_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )

        if conversation is None:
            return []

        return message_repository.get_by_conversation(
            db=db,
            conversation_id=conversation_id,
        )


conversation_service = ConversationService()
