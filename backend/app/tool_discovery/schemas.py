from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=4000)
    conversation_context: str | None = Field(default=None, max_length=4000)
    desired_outcome: str | None = Field(default=None, max_length=500)
    required_capabilities: list[str] = Field(default_factory=list, max_length=20)
    expected_input: dict = Field(default_factory=dict)
    environment: str = "production"
    data_classification: str = "internal"
    risk_tolerance: Literal["read", "write", "destructive"] = "read"
    max_cost: float | None = Field(default=None, ge=0)
    latency_preference: Literal["low", "balanced", "quality"] = "balanced"
    approval_allowed: bool = False
    max_candidates: int = Field(default=8, ge=1, le=20)
    explicit_tool: str | None = Field(default=None, max_length=100)
    prohibited_tools: list[str] = Field(default_factory=list, max_length=20)
    multi_tool: bool = False


class StructuredIntent(BaseModel):
    action: str
    domain: str
    operation: Literal["read", "write", "delete", "send"]
    environment: str
    expected_output: str
    required_inputs: list[str]
    data_sensitivity: str
    external_communication: bool
    destructive: bool
    keywords: list[str]
    ambiguous: bool = False


class PolicyDecision(BaseModel):
    decision: Literal["allow", "deny", "approval_required"]
    policy_ids: list[str] = []
    reason_codes: list[str] = []
    approval_required: bool = False
    safe_explanation: str
    evaluation_version: str = "1.0.0"
