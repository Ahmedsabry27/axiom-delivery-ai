from app.actions.contracts.action import Action
from app.actions.models.action_result import ActionResult


class GenerateDeploymentReportAction(Action):
    name = "generate-deployment-report"

    async def execute(
        self,
        input_data: dict,
    ) -> ActionResult:

        return ActionResult(
            success=True,
            action_name=self.name,
            output={"report": "Deployment report generated"},
        )
