from app.ai.adapters.bedrock_adapter import BedrockAdapter
from app.ai.models import AIMessage, AIMessageRole
from app.ai.providers.bedrock_provider import BedrockProvider


def test_bedrock_converse_system_prompt_is_not_nested():
    system, messages = BedrockAdapter.to_messages(
        [
            AIMessage(AIMessageRole.SYSTEM, "Governed instructions"),
            AIMessage(AIMessageRole.USER, "Summarize status"),
        ]
    )
    request = BedrockProvider("amazon.nova-lite-v1:0")._build_request(
        system_prompt=system, conversation=messages
    )
    assert request["system"] == [{"text": "Governed instructions"}]
    assert isinstance(request["system"][0]["text"], str)
    assert request["messages"][0]["content"] == [{"text": "Summarize status"}]


def test_nova_lite_uses_us_inference_profile_without_changing_published_model(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.ai.providers.bedrock_provider.settings.AWS_REGION", "us-east-1"
    )
    monkeypatch.setattr(
        "app.ai.providers.bedrock_provider.settings.BEDROCK_INFERENCE_PROFILE_ID", None
    )
    provider = BedrockProvider("amazon.nova-lite-v1:0")
    request = provider._build_request(system_prompt=None, conversation=[])
    assert provider.model == "amazon.nova-lite-v1:0"
    assert request["modelId"] == "us.amazon.nova-lite-v1:0"
