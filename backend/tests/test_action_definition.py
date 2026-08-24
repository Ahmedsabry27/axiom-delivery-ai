from app.actions.models.action_definition import (
    ActionDefinition,
)


def test_action_definition_creation():

    definition = ActionDefinition(
        name="deploy-action",
        description=("Deploy application"),
        category="deployment",
        required_permissions=["deployment.execute"],
        supported_agents=["deployment-agent"],
    )

    assert definition.name == "deploy-action"

    assert definition.category == "deployment"

    assert "deployment.execute" in definition.required_permissions

    assert "deployment-agent" in definition.supported_agents
