from app.ai.governed_provider import (
    authorized_provider_invocation,
    provider_invocation_authorized,
)


def test_provider_authorization_reports_actual_context_state():
    assert provider_invocation_authorized() is False
    with authorized_provider_invocation():
        assert provider_invocation_authorized() is True
    assert provider_invocation_authorized() is False
