from app.actions.models.action_permission import (
    ActionPermission,
)
from app.actions.models.action_request import (
    ActionRequest,
)
from app.actions.services.action_permission_validator import (
    ActionPermissionValidator,
)


def test_permission_granted():

    validator = ActionPermissionValidator()

    validator.register_permission(
        ActionPermission(
            action_name="deploy-release",
            allowed_roles=["release-manager"],
        )
    )

    request = ActionRequest(
        action_name="deploy-release",
        user_id="user1",
        roles=["release-manager"],
    )

    assert validator.validate(request) is True


def test_permission_denied():

    validator = ActionPermissionValidator()

    validator.register_permission(
        ActionPermission(
            action_name="deploy-release",
            allowed_roles=["admin"],
        )
    )

    request = ActionRequest(
        action_name="deploy-release",
        user_id="user1",
        roles=["developer"],
    )

    assert validator.validate(request) is False


def test_unknown_action_denied():

    validator = ActionPermissionValidator()

    request = ActionRequest(
        action_name="unknown",
        user_id="user1",
        roles=[],
    )

    assert validator.validate(request) is False
