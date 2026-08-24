from app.actions.services.action_repository import ActionRepository


def test_register_action(
    db_session,
):

    repository = ActionRepository(db_session)

    action = repository.register_action(
        name="generate-report",
        action_type="REPORT",
    )

    assert action.id is not None
    assert action.name == "generate-report"
    assert action.type == "REPORT"


def test_list_actions(
    db_session,
):

    repository = ActionRepository(db_session)

    repository.register_action(
        "send-email",
        "NOTIFICATION",
    )

    actions = repository.list_actions()

    assert len(actions) == 1
    assert actions[0].name == "send-email"


def test_update_permissions(
    db_session,
):

    repository = ActionRepository(db_session)

    action = repository.register_action(
        "deploy",
        "DEPLOYMENT",
    )

    updated = repository.update_permissions(
        action.id,
        {"role": "admin"},
    )

    assert updated.permissions == {"role": "admin"}
