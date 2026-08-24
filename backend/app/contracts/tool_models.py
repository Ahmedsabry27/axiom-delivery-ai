"""Public, stable Tool SDK value types."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TOOL_NAME = re.compile(r"^[a-z][a-z0-9]*(?:[._][a-z0-9]+)*$")
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
SECRET_WORDS = {
    "password",
    "secret",
    "token",
    "credential",
    "api_key",
    "private_key",
    "connection_string",
}


class RiskLevel(StrEnum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_attempts: int = Field(default=1, ge=1, le=5)
    base_delay_seconds: float = Field(default=0.25, ge=0, le=10)


class ToolMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    display_name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    category: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    provider: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    version: str
    author: str = Field(default="Platform Team", max_length=120)
    tags: tuple[str, ...] = ()
    enabled: bool = True
    parameters: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    permissions: tuple[str, ...] = ()
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    retry_policy: RetryPolicy = RetryPolicy()
    idempotent: bool = True
    risk_level: RiskLevel = RiskLevel.READ
    deprecated: bool = False
    configuration_requirements: tuple[str, ...] = ()

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if not TOOL_NAME.fullmatch(value) or len(value) > 100:
            raise ValueError(
                "tool names must be <=100 characters using lowercase segments"
            )
        return value

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        if not SEMVER.fullmatch(value):
            raise ValueError("version must be semantic versioning (for example 1.0.0)")
        return value

    @model_validator(mode="after")
    def validate_schemas(self):
        schema = self.parameters
        if schema.get("type") != "object":
            raise ValueError("parameters must be a JSON Schema object")
        if schema.get("additionalProperties", True):
            raise ValueError("parameter schemas must set additionalProperties=false")
        serialized = str(schema)
        if len(serialized) > 64_000 or len(schema.get("properties", {})) > 100:
            raise ValueError("parameter schema exceeds safety limits")
        try:
            Draft202012Validator.check_schema(schema)
            if self.output_schema:
                Draft202012Validator.check_schema(self.output_schema)
        except Exception as exc:
            raise ValueError(f"invalid JSON Schema: {exc.message}") from exc
        for key in schema.get("properties", {}):
            if key.lower() in SECRET_WORDS or any(
                word in key.lower() for word in SECRET_WORDS
            ):
                raise ValueError(
                    f"credential field '{key}' may not be a tool parameter"
                )
        if (
            self.risk_level != RiskLevel.READ
            and self.retry_policy.max_attempts > 1
            and not self.idempotent
        ):
            raise ValueError("unsafe non-idempotent tools cannot be retried")
        return self

    def model_tool_definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ExecutionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: str
    permissions: set[str] = Field(default_factory=set)
    roles: set[str] = Field(default_factory=set)
    groups: set[str] = Field(default_factory=set)
    tenant_id: str = "default"
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str | None = None
    conversation_id: str | None = None
    agent_id: str | None = None
    environment: str = "production"
    data_classification: str = "internal"
    approval_granted: bool = False
    approval_request_id: str | None = None
    approval_resume_token: str | None = Field(default=None, exclude=True, repr=False)
    max_cost: float | None = None
    idempotency_key: str | None = None
    internal: bool = False
    deadline: datetime | None = None
    db_session: Any = Field(default=None, exclude=True, repr=False)


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parameters: dict[str, Any] = Field(default_factory=dict)
    version: str | None = None


class ToolError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    fields: list[dict[str, str]] = Field(default_factory=list)


class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: ToolError | None = None
    warnings: list[str] = Field(default_factory=list)
    pagination: dict[str, Any] | None = None
    provider_request_id: str | None = None

    @classmethod
    def succeeded(cls, data: Any, **kwargs) -> ToolResult:
        return cls(success=True, data=data, **kwargs)

    @classmethod
    def failed(cls, code: str, message: str, retryable: bool = False) -> ToolResult:
        return cls(
            success=False,
            error=ToolError(code=code, message=message, retryable=retryable),
        )


class ExecutionEnvelope(BaseModel):
    execution_id: str
    tool: dict[str, str]
    status: Literal["succeeded", "failed", "timed_out", "cancelled"]
    data: Any = None
    error: ToolError | None = None
    meta: dict[str, Any]
