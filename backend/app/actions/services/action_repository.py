from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.database.models.action import Action


class ActionRepository:
    """
    Persistence layer for actions.

    Responsibilities:
    - Register actions
    - Retrieve actions
    - List actions
    - Update permissions
    """

    def __init__(
        self,
        db: Session,
    ) -> None:

        self._db = db

    def register_action(
        self,
        name: str,
        action_type: str,
        permissions: dict | None = None,
    ) -> Action:
        """
        Persist action definition.
        """

        action = Action(
            name=name,
            type=action_type,
            permissions=permissions or {},
            created_at=datetime.now(UTC),
        )

        self._db.add(action)

        self._db.commit()

        self._db.refresh(action)

        return action

    def get_action(
        self,
        action_id: int,
    ) -> Action | None:

        return self._db.get(
            Action,
            action_id,
        )

    def get_action_by_name(
        self,
        name: str,
    ) -> Action | None:

        return self._db.query(Action).filter(Action.name == name).first()

    def list_actions(
        self,
    ) -> list[Action]:

        return self._db.query(Action).all()

    def update_permissions(
        self,
        action_id: int,
        permissions: dict,
    ) -> Action | None:

        action = self.get_action(action_id)

        if action is None:
            return None

        action.permissions = permissions

        self._db.commit()

        self._db.refresh(action)

        return action
