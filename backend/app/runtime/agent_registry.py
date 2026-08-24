class AgentRegistry:
    def get_agent(self, name: str):

        agents = {
            "ReportingAgent": self.reporting_agent,
            "GeneralAssistantAgent": self.general_agent,
        }

        return agents.get(name)

    def reporting_agent(self, task):

        return {
            "result": "Deployment report generated",
        }

    def general_agent(self, task):

        return {
            "result": "AI response generated",
        }
