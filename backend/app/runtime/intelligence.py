from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.ai.factory import AIProviderFactory
from app.ai.models import AIMessage, AIMessageRole


@dataclass(slots=True)
class ParameterValue:
    value: Any
    source: str
    confidence: float
    status: str = "resolved"


@dataclass(slots=True)
class IntentAnalysis:
    intent: str = "general.assistance"
    domain: str = "general"
    operation: str = "respond"
    resource: str = "unknown"
    entities: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    required_capabilities: list[str] = field(default_factory=list)
    selected_tool: str | None = None
    ambiguous: bool = False

    def safe_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "domain": self.domain,
            "operation": self.operation,
            "resource": self.resource,
            "entities": self.entities,
            "confidence": self.confidence,
            "required_capabilities": self.required_capabilities,
            "selected_tool": self.selected_tool,
            "ambiguous": self.ambiguous,
        }


def _json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if "```" in cleaned:
        cleaned = re.sub(r"^.*?```(?:json)?\s*|\s*```.*$", "", cleaned, flags=re.DOTALL)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model did not return a JSON object")
    value = json.loads(cleaned[start : end + 1])
    return value if isinstance(value, dict) else {}


class CapabilityIntelligence:
    """Model-led semantic analysis constrained to registered capability schemas."""

    @staticmethod
    def _catalog(definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "name": fn.get("name"),
                "description": fn.get("description"),
                "parameters": fn.get("parameters") or {},
            }
            for item in definitions
            if (fn := item.get("function") or {}).get("name")
        ]

    def analyze(
        self,
        message: str,
        definitions: list[dict[str, Any]],
        *,
        provider_name: str,
        model: str,
        conversation_context: str = "",
        semantic_intent: dict[str, Any] | None = None,
    ) -> IntentAnalysis:
        catalog = self._catalog(definitions)
        if not catalog:
            return IntentAnalysis()
        prompt = (
            "Resolve the already-classified enterprise request to one capability from CATALOG or null. "
            "Extract only values supported by that capability's JSON Schema. Never map a request "
            "to a different named domain merely because both mention report. Do not reclassify or "
            "change SEMANTIC_INTENT. Return JSON only with entities, confidence, "
            "required_capabilities, selected_tool, ambiguous. "
            f"\nCATALOG={json.dumps(catalog, default=str)}"
            f"\nSEMANTIC_INTENT={json.dumps(semantic_intent or {}, default=str)}"
            f"\nCONVERSATION={conversation_context[-3000:]}\nREQUEST={message}"
        )
        try:
            provider = AIProviderFactory.get_provider(
                provider_name=provider_name, model=model
            )
            response = provider.ask(
                [
                    AIMessage(
                        role=AIMessageRole.SYSTEM,
                        content="You are a constrained capability and parameter resolver.",
                    ),
                    AIMessage(role=AIMessageRole.USER, content=prompt),
                ]
            )
            raw = _json_object(response.text)
            names = {item["name"] for item in catalog}
            selected = (
                raw.get("selected_tool") if raw.get("selected_tool") in names else None
            )
            entities = (
                raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
            )
            if selected:
                schema = next(
                    item["parameters"] for item in catalog if item["name"] == selected
                )
                entities = {
                    key: value
                    for key, value in entities.items()
                    if key in (schema.get("properties") or {})
                }
            semantic = semantic_intent or {}
            return IntentAnalysis(
                intent=str(semantic.get("intent") or "general.assistance"),
                domain=str(semantic.get("domain") or "general"),
                operation=str(semantic.get("operation") or "respond"),
                resource=str(semantic.get("resource") or "unknown"),
                entities=entities,
                confidence=max(0.0, min(1.0, float(raw.get("confidence", 0.5)))),
                required_capabilities=[
                    str(x)
                    for x in raw.get("required_capabilities", [])
                    if isinstance(x, str)
                ],
                selected_tool=selected,
                ambiguous=bool(semantic.get("ambiguous", raw.get("ambiguous", False))),
            )
        except Exception:  # noqa: BLE001 - preserve deterministic compatibility fallback
            return self.fallback(message, catalog)

    @staticmethod
    def fallback(message: str, catalog: list[dict[str, Any]]) -> IntentAnalysis:
        """Deterministic safety fallback; model analysis remains the primary path."""
        lowered = message.lower()
        tokens = set(re.findall(r"[a-z0-9_.-]+", lowered))
        explicit_domains = {
            name.split(".", 1)[0]
            for name in (item["name"] for item in catalog)
            if name.split(".", 1)[0] in tokens
        }
        ranked = []
        for item in catalog:
            name = item["name"]
            parts = set(name.replace("_", ".").split("."))
            doc = set(
                re.findall(r"[a-z0-9_.-]+", f"{name} {item['description']}".lower())
            )
            domain = name.split(".", 1)[0]
            if explicit_domains and domain not in explicit_domains:
                continue
            score = len(tokens & doc) + 2 * len(tokens & parts)
            if (
                "report" in tokens
                and "report" not in doc
                and domain not in explicit_domains
            ):
                score -= 2
            ranked.append((score, item))
        ranked.sort(key=lambda row: row[0], reverse=True)
        if "report" in tokens and explicit_domains:
            readable = [
                row
                for row in ranked
                if any(word in row[1]["name"] for word in ("search", "list", "get"))
            ]
            if readable:
                ranked = readable
        selected = ranked[0][1] if ranked and ranked[0][0] >= 2 else None
        if not selected:
            return IntentAnalysis(ambiguous=True)
        name = selected["name"]
        domain = name.split(".", 1)[0]
        parts = name.replace("_", ".").split(".")
        operation = (
            "create"
            if "create" in parts
            else "search"
            if "search" in parts
            else "report"
            if "report" in parts
            else "read"
        )
        entities = CapabilityIntelligence._extract_schema_values(
            message, selected["parameters"]
        )
        return IntentAnalysis(
            intent=f"{domain}.{parts[-2] if len(parts) > 2 else 'resource'}.{operation}",
            domain=domain,
            operation=operation,
            resource=parts[-2] if len(parts) > 2 else parts[-1],
            entities=entities,
            confidence=0.82,
            required_capabilities=[name],
            selected_tool=name,
            ambiguous="report" in tokens
            and operation in {"search", "read"}
            and not entities,
        )

    @staticmethod
    def _extract_schema_values(message: str, schema: dict[str, Any]) -> dict[str, Any]:
        properties = schema.get("properties") or {}
        values: dict[str, Any] = {}
        # Generic label/value extraction derived from schema keys rather than intents.
        boundaries = "|".join(re.escape(key.replace("_", " ")) for key in properties)
        for key, definition in properties.items():
            label = re.escape(key.replace("_", " "))
            match = re.search(
                rf"\b{label}\b\s*(?:is|=|:)?\s+(.+?)(?=\s+(?:{boundaries})\b|$)",
                message,
                re.IGNORECASE,
            )
            if match:
                value = match.group(1).strip(" ,.;\"'")
                if value:
                    values[key] = value
            enum = definition.get("enum") or []
            enum_match = next(
                (
                    item
                    for item in enum
                    if re.search(rf"\b{re.escape(str(item))}\b", message, re.IGNORECASE)
                ),
                None,
            )
            if enum_match is not None:
                values[key] = enum_match
        if "project_key" in properties and "project_key" not in values:
            match = re.search(
                r"\bproject\s+([A-Z][A-Z0-9_-]{1,14})\b", message, re.IGNORECASE
            )
            if not match:
                match = re.search(
                    r"\bin\s+(?!project\b)([A-Z][A-Z0-9_-]{1,14})\b",
                    message,
                    re.IGNORECASE,
                )
            if not match:
                candidates = re.findall(r"\b[A-Z][A-Z0-9_-]{1,14}\b", message)
                candidates = [
                    item
                    for item in candidates
                    if item.upper()
                    not in {"TASK", "BUG", "STORY", "EPIC", "FEATURE", "SUBTASK"}
                ]
                match = (
                    re.match(r"(.+)", candidates[0]) if len(candidates) == 1 else None
                )
            if match:
                values["project_key"] = match.group(1)
        if "issue_type" in properties and "issue_type" not in values:
            match = re.search(
                r"\b(?:type\s+)?(Bug|Task|Story|Epic|Feature|Subtask)\b",
                message,
                re.IGNORECASE,
            )
            if match:
                values["issue_type"] = match.group(1).title()
        if "summary" in properties and "summary" not in values:
            match = re.search(
                r"\b(?:summary\s+(?:is\s+)?|called\s+)(.+)$", message, re.IGNORECASE
            )
            if match:
                values["summary"] = match.group(1).strip(" ,.;\"'")
        return values


def reconcile_parameters(
    schema: dict[str, Any],
    *,
    prompt_values: dict[str, Any],
    collected_values: dict[str, Any],
    context_values: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    properties = schema.get("properties") or {}
    resolved: dict[str, Any] = {}
    trace: dict[str, dict[str, Any]] = {}
    # Stronger sources are applied last.
    for source, confidence, values in (
        ("conversation_context", 0.75, context_values or {}),
        ("required_input", 1.0, collected_values),
        ("user_prompt", 0.95, prompt_values),
    ):
        for key, value in values.items():
            if key in properties and value not in (None, "", []):
                normalization = properties[key].get("x-normalize")
                if isinstance(value, str) and normalization == "uppercase":
                    value = value.strip().upper()
                elif isinstance(value, str) and normalization == "lowercase":
                    value = value.strip().lower()
                elif isinstance(value, str) and normalization == "trim":
                    value = value.strip()
                resolved[key] = value
                trace[key] = {
                    "value": value,
                    "source": source,
                    "confidence": confidence,
                    "status": "resolved",
                }
    return resolved, trace
