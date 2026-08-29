import httpx
import pytest
from botocore.exceptions import ReadTimeoutError
from openai import APITimeoutError
from pydantic import BaseModel

from app.ai.exceptions import AITimeoutError
from app.ai.models import AIMessage, AIMessageRole
from app.ai.providers.bedrock_provider import BedrockProvider
from app.ai.providers.openai_provider import OpenAIProvider


def message():
    return [AIMessage(role=AIMessageRole.USER, content="test")]


def test_openai_sdk_timeout_is_normalized(monkeypatch):
    class Responses:
        def create(self, **_kwargs):
            raise APITimeoutError(
                request=httpx.Request("POST", "https://api.openai.com")
            )

    monkeypatch.setattr(
        "app.ai.providers.openai_provider.get_openai_client",
        lambda: type("Client", (), {"responses": Responses()})(),
    )
    with pytest.raises(AITimeoutError):
        OpenAIProvider("test-model").ask(message())


def test_bedrock_sdk_timeout_is_normalized(monkeypatch):
    class Client:
        def converse(self, **_kwargs):
            raise ReadTimeoutError(endpoint_url="https://bedrock.example")

    monkeypatch.setattr(
        "app.ai.providers.bedrock_provider.get_bedrock_client", lambda: Client()
    )
    with pytest.raises(AITimeoutError):
        BedrockProvider("test-model").ask(message())


def test_openai_structured_response_uses_native_parse(monkeypatch):
    class Output(BaseModel):
        value: str

    parsed = Output(value="ok")

    class Responses:
        def parse(self, **kwargs):
            assert kwargs["text_format"] is Output
            return type(
                "Response",
                (),
                {
                    "output_parsed": parsed,
                    "output_text": '{"value":"ok"}',
                    "id": "response-1",
                    "usage": None,
                },
            )()

    monkeypatch.setattr(
        "app.ai.providers.openai_provider.get_openai_client",
        lambda: type("Client", (), {"responses": Responses()})(),
    )

    response, output = OpenAIProvider("test-model").ask_structured(
        message(), response_model=Output
    )

    assert response.response_id == "response-1"
    assert output == parsed
