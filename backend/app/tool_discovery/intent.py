from __future__ import annotations

import re

from app.tool_discovery.schemas import StructuredIntent

WRITE = {
    "create",
    "update",
    "change",
    "deploy",
    "publish",
    "approve",
    "configure",
    "generate",
    "prepare",
}
DELETE = {"delete", "remove", "destroy", "terminate", "revoke"}
SEND = {"send", "notify", "email", "message", "alert"}
STOP = {"the", "a", "an", "to", "for", "and", "of", "in", "on", "with", "please", "me"}


def extract_intent(query, environment="production", classification="internal"):
    clean = re.sub(r"[^a-z0-9_\- ]", " ", query.lower())[:4000]
    words = [x for x in clean.split() if x not in STOP]
    operation = (
        "delete"
        if set(words) & DELETE
        else "send"
        if set(words) & SEND
        else "write"
        if set(words) & WRITE
        else "read"
    )
    action = words[0] if words else "unknown"
    domain = " ".join(words[1:4]) or "general"
    explicit_env = next(
        (
            x
            for x in words
            if x in {"production", "prod", "staging", "development", "dev"}
        ),
        environment,
    )
    return StructuredIntent(
        action=action,
        domain=domain,
        operation=operation,
        environment="production"
        if explicit_env == "prod"
        else "development"
        if explicit_env == "dev"
        else explicit_env,
        expected_output="report"
        if "report" in words or "summary" in words
        else "result",
        required_inputs=[],
        data_sensitivity=classification,
        external_communication=operation == "send",
        destructive=operation == "delete",
        keywords=words[:30],
        ambiguous=len(words) < 2,
    )
