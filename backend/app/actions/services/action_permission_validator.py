from __future__ import annotations

from app.actions.models.action_permission import (
    ActionPermission,
)
from app.actions.models.action_request import (
    ActionRequest,
)


class ActionPermissionValidator:
    """
    Validates whether a user can execute an action.
    """

    def __init__(self):

        self._permissions: dict[str, ActionPermission] = {}

    def register_permission(
        self,
        permission: ActionPermission,
    ) -> None:

        self._permissions[permission.action_name] = permission

    def validate(
        self,
        request: ActionRequest,
    ) -> bool:

        permission = self._permissions.get(request.action_name)

        if permission is None:
            return False

        if not permission.allowed_roles:
            return True

        return any(role in permission.allowed_roles for role in request.roles)
