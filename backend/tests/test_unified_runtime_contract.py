from uuid import uuid4

from app.models.chat import ChatRequest
from app.services.runtime_execution_service import RuntimeExecutionService


def test_chat_request_supports_unified_runtime_context():
    request = ChatRequest(
        message="Analyze deployment health",
        conversation_id=uuid4(),
        agent_id="agent-1",
        provider="bedrock",
        model="amazon.nova-lite-v1:0",
        workspace_id="finance",
        metadata={"environment": "Production"},
    )
    assert request.workspace_id == "finance"
    assert request.metadata == {"environment": "Production"}


def test_required_fields_are_derived_from_authorized_tool_schema():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "deployment_report",
                "description": "Generate a deployment report",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "environment": {
                            "type": "string",
                            "enum": ["Production", "Staging"],
                        },
                        "include_failed": {"type": "boolean"},
                        "report_format": {"type": "string", "enum": ["PDF", "HTML"]},
                        "recipients": {"type": "string", "format": "email"},
                    },
                    "required": [
                        "environment",
                        "include_failed",
                        "report_format",
                        "recipients",
                    ],
                },
            },
        }
    ]
    fields = RuntimeExecutionService._required_fields(
        "Generate a deployment report and send it to leadership", {}, tools
    )
    assert {field["name"] for field in fields} == {
        "environment",
        "include_failed",
        "report_format",
        "recipients",
    }
    assert all("label" in field and "type" in field for field in fields)


def test_supplied_continuation_values_are_not_requested_again():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "deployment_report",
                "description": "Generate a deployment report",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "environment": {"type": "string"},
                        "include_failed": {"type": "boolean"},
                        "report_format": {"type": "string"},
                    },
                    "required": ["environment", "include_failed", "report_format"],
                },
            },
        }
    ]
    fields = RuntimeExecutionService._required_fields(
        "Generate a deployment report",
        {"environment": "Production", "include_failed": True, "report_format": "PDF"},
        tools,
    )
    assert fields == []


def test_business_placeholders_are_rejected_unless_a_template_was_requested():
    assert RuntimeExecutionService._has_unresolved_business_placeholders(
        "Report for [Project Name]", "Generate a deployment report"
    )
    assert not RuntimeExecutionService._has_unresolved_business_placeholders(
        "Report for [Project Name]", "Give me a deployment report template"
    )
