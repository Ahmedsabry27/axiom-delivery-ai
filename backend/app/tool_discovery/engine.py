from __future__ import annotations

import logging
import re
import time
from collections import Counter
from datetime import UTC, datetime, timedelta

from prometheus_client import Counter as MetricCounter
from prometheus_client import Histogram

from app.database.models.tool import ToolExecution
from app.database.models.tool_discovery import (
    ToolCandidateDecision,
    ToolDiscoveryEvent,
    ToolMarketplaceProfile,
    ToolSearchIndex,
)
from app.tool_discovery import STRATEGY_VERSION
from app.tool_discovery.embedding import cosine, provider
from app.tool_discovery.governance import evaluate
from app.tool_discovery.indexing import index_tools
from app.tool_discovery.intent import extract_intent
from app.tool_sdk.service import registry

DISCOVERIES = MetricCounter(
    "tool_discovery_total", "Tool discovery outcomes", ["outcome"]
)
DISCOVERY_DURATION = Histogram(
    "tool_discovery_duration_seconds", "Tool discovery duration"
)
CANDIDATES = Histogram(
    "tool_discovery_candidate_count", "Candidates before authorization"
)
ELIGIBLE = Histogram("tool_discovery_eligible_count", "Eligible candidates")
logger = logging.getLogger(__name__)


def _tokens(value):
    return set(re.findall(r"[a-z0-9_]+", value.lower()))


def _lexical(query, document):
    q, d = _tokens(query), _tokens(document)
    if not q:
        return 0
    return len(q & d) / len(q)


def _input_score(schema, provided):
    required = set(schema.get("required", []))
    if not required:
        return 1.0, []
    missing = sorted(required - set(provided))
    return max(0, 1 - len(missing) / len(required)), missing


def _confidence(rows):
    if not rows:
        return "low"
    top = rows[0]["score"]
    margin = top - (rows[1]["score"] if len(rows) > 1 else 0)
    return (
        "high"
        if top >= 0.55 and margin >= 0.08 and not rows[0]["missing_inputs"]
        else "medium"
        if top >= 0.28 and margin >= 0.03
        else "low"
    )


class ToolDiscoveryEngine:
    async def discover(self, request, context, db, *, simulate=False):
        started = time.perf_counter()
        intent = extract_intent(
            request.query, request.environment, request.data_classification
        )
        context = context.model_copy(
            update={
                "environment": request.environment,
                "data_classification": request.data_classification,
                "max_cost": request.max_cost,
            }
        )
        await index_tools(db, context.tenant_id)
        query_vector = await provider.embed_query(
            " ".join([request.query, *request.required_capabilities])
        )
        indexes = (
            db.query(ToolSearchIndex)
            .filter_by(tenant_id=context.tenant_id, index_status="ready")
            .all()
        )
        candidates = []
        rejections = Counter()
        since = datetime.now(UTC) - timedelta(days=30)
        for idx in indexes:
            try:
                tool = registry.get(idx.tool_name, idx.tool_version)
            except Exception:  # noqa: BLE001 -- one broken plugin must not abort discovery
                logger.warning("Skipped unavailable discovery candidate", exc_info=True)
                continue
            if request.explicit_tool and tool.name != request.explicit_tool:
                continue
            if tool.name in request.prohibited_tools:
                continue
            profile = (
                db.query(ToolMarketplaceProfile)
                .filter_by(
                    tenant_id=context.tenant_id,
                    tool_name=tool.name,
                    tool_version=tool.metadata.version,
                )
                .first()
            )
            decision = evaluate(db, tool, context, intent, profile)
            if decision.decision == "deny":
                rejections[decision.reason_codes[0]] += 1
                continue
            if (
                request.max_cost is not None
                and profile.estimated_cost is not None
                and profile.estimated_cost > request.max_cost
            ):
                rejections["COST_LIMIT_EXCEEDED"] += 1
                continue
            risk_order = {"read": 0, "write": 1, "destructive": 2}
            if (
                risk_order[tool.metadata.risk_level.value]
                > risk_order[request.risk_tolerance]
            ):
                rejections["RISK_LIMIT_EXCEEDED"] += 1
                continue
            executions = (
                db.query(ToolExecution)
                .filter(
                    ToolExecution.tenant_id == context.tenant_id,
                    ToolExecution.tool_name == tool.name,
                    ToolExecution.started_at >= since,
                )
                .all()
            )
            success = (
                sum(x.status == "succeeded" for x in executions) / len(executions)
                if executions
                else 0.8
            )
            latency = (
                sum((x.duration_ms or 0) for x in executions) / len(executions)
                if executions
                else 500
            )
            semantic = cosine(query_vector, idx.embedding)
            lexical = _lexical(request.query, idx.search_document)
            exact = (
                1.0
                if request.explicit_tool == tool.name
                or tool.name.replace("_", " ") in request.query.lower()
                else 0
            )
            capability = len(
                set(request.required_capabilities) & set(tool.metadata.tags)
            ) / max(1, len(request.required_capabilities))
            input_score, missing = _input_score(
                tool.metadata.parameters, request.expected_input
            )
            health = 1 if profile.health_status == "healthy" else 0.55
            risk = {"read": 1, "write": 0.65, "destructive": 0.25}[
                tool.metadata.risk_level.value
            ]
            latency_score = 1 / (1 + latency / 1500)
            cost_score = (
                1
                if profile.estimated_cost is None
                else 1 / (1 + profile.estimated_cost)
            )
            score = (
                0.28 * semantic
                + 0.24 * lexical
                + 0.14 * exact
                + 0.08 * capability
                + 0.1 * input_score
                + 0.06 * success
                + 0.04 * health
                + 0.025 * risk
                + 0.02 * latency_score
                + 0.015 * cost_score
            )
            candidates.append(
                {
                    "tool_name": tool.name,
                    "version": tool.metadata.version,
                    "display_name": tool.metadata.display_name,
                    "description": tool.metadata.description,
                    "source": profile.source,
                    "category": tool.metadata.category,
                    "provider": tool.metadata.provider,
                    "risk": tool.metadata.risk_level.value,
                    "health": profile.health_status,
                    "approval_required": decision.decision == "approval_required",
                    "required_permissions": list(tool.metadata.permissions),
                    "missing_inputs": missing,
                    "estimated_cost": profile.estimated_cost,
                    "expected_latency_ms": round(latency, 2),
                    "success_rate": round(success, 4),
                    "score": round(score, 6),
                    "component_scores": {
                        "semantic": round(semantic, 4),
                        "lexical": round(lexical, 4),
                        "exact": exact,
                        "capability": round(capability, 4),
                        "input": round(input_score, 4),
                        "success": round(success, 4),
                        "health": health,
                        "risk": risk,
                        "latency": round(latency_score, 4),
                        "cost": round(cost_score, 4),
                    },
                    "reason_codes": [
                        *decision.reason_codes,
                        "INTENT_MATCH"
                        if semantic + lexical > 0.2
                        else "WEAK_INTENT_MATCH",
                        "INPUT_COMPATIBLE" if not missing else "INPUT_REQUIRED",
                    ],
                }
            )
        candidates.sort(key=lambda x: (-x["score"], x["tool_name"], x["version"]))
        candidates = candidates[: request.max_candidates]
        if candidates and candidates[0]["score"] < 0.20:
            candidates = []
        confidence = _confidence(candidates)
        selected = candidates[0] if candidates else None
        if not candidates:
            outcome = "no_authorized_tool" if rejections else "no_matching_tool"
        elif intent.ambiguous or confidence == "low":
            outcome = "clarification_required"
        elif selected["approval_required"]:
            outcome = "approval_required"
        elif selected["missing_inputs"]:
            outcome = "input_required"
        elif request.multi_tool and len(candidates) > 1:
            outcome = "multiple_candidates"
        else:
            outcome = "selected"
        duration = round((time.perf_counter() - started) * 1000, 2)
        event = ToolDiscoveryEvent(
            tenant_id=context.tenant_id,
            actor_id=context.actor_id,
            agent_id=context.agent_id,
            conversation_id=context.conversation_id,
            safe_intent=intent.model_dump(),
            candidate_count=len(indexes),
            eligible_count=len(candidates),
            selected_tool=selected["tool_name"]
            if selected and outcome in {"selected", "approval_required"}
            else None,
            selected_version=selected["version"]
            if selected and outcome in {"selected", "approval_required"}
            else None,
            confidence=confidence,
            outcome=outcome,
            strategy_version=STRATEGY_VERSION,
            embedding_model=provider.model,
            duration_ms=duration,
            correlation_id=context.correlation_id,
        )
        db.add(event)
        db.flush()
        clarification = None
        clarification_token = None
        approval = None
        approval_token = None
        if (
            selected
            and outcome in {"clarification_required", "input_required"}
            and not simulate
        ):
            from app.governance.clarifications import create_clarification

            selected_tool = registry.get(selected["tool_name"], selected["version"])
            clarification, clarification_token = create_clarification(
                db,
                discovery_id=event.id,
                tool=selected_tool,
                context=context,
                known_values=request.expected_input,
                missing_fields=selected["missing_inputs"],
                alternatives=candidates,
            )
        if selected and outcome == "approval_required" and not simulate:
            from app.governance.workflows import create_approval

            selected_tool = registry.get(selected["tool_name"], selected["version"])
            selected_policy = evaluate(db, selected_tool, context, intent)
            approval, approval_token = create_approval(
                db,
                tool=selected_tool,
                normalized_input=request.expected_input,
                context=context,
                policy_ids=selected_policy.policy_ids,
            )
            approval.discovery_id = event.id
        for rank, row in enumerate(candidates, 1):
            db.add(
                ToolCandidateDecision(
                    discovery_id=event.id,
                    tenant_id=context.tenant_id,
                    tool_name=row["tool_name"],
                    tool_version=row["version"],
                    eligible=True,
                    component_scores=row["component_scores"],
                    final_score=row["score"],
                    rank=rank,
                    selected=selected is row
                    and outcome in {"selected", "approval_required"},
                )
            )
        for code, count in rejections.items():
            db.add(
                ToolCandidateDecision(
                    discovery_id=event.id,
                    tenant_id=context.tenant_id,
                    tool_name=None,
                    tool_version=None,
                    eligible=False,
                    exclusion_code=code,
                    component_scores={"count": count},
                    final_score=0,
                    selected=False,
                )
            )
        from app.audit.events import append_audit_event

        append_audit_event(
            db,
            tenant_id=context.tenant_id,
            actor_id=context.actor_id,
            action="tool.discovery.completed",
            target_type="tool_discovery",
            target_id=event.id,
            correlation_id=context.correlation_id,
            after={
                "outcome": outcome,
                "selected_tool": event.selected_tool,
                "confidence": confidence,
            },
        )
        db.commit()
        DISCOVERIES.labels(outcome).inc()
        DISCOVERY_DURATION.observe(duration / 1000)
        CANDIDATES.observe(len(indexes))
        ELIGIBLE.observe(len(candidates))
        return {
            "discovery_id": event.id,
            "outcome": outcome,
            "safe_intent": intent.model_dump(),
            "selected": selected
            if outcome in {"selected", "approval_required"}
            else None,
            "candidates": candidates,
            "safe_rejections": [{"reason_code": k} for k in sorted(rejections)],
            "confidence": confidence,
            "explanation": "Selection uses authorized hybrid relevance, input compatibility, health, quality, latency, cost, and risk signals.",
            "missing_inputs": selected["missing_inputs"] if selected else [],
            "human_confirmation_required": outcome
            in {
                "clarification_required",
                "input_required",
                "approval_required",
                "multiple_candidates",
            },
            "clarification": {
                "id": clarification.id,
                "question": clarification.question,
                "input_schema": clarification.input_schema,
                "known_values": clarification.known_values,
                "missing_fields": clarification.missing_fields,
                "expires_at": clarification.expires_at.isoformat(),
                "resume_token": clarification_token,
            }
            if clarification
            else None,
            "approval": {
                "id": approval.id,
                "status": approval.status,
                "tool": approval.tool_name,
                "version": approval.tool_version,
                "expires_at": approval.expires_at.isoformat(),
                "resume_token": approval_token,
            }
            if approval
            else None,
            "strategy_version": STRATEGY_VERSION,
            "embedding_model": provider.model,
            "correlation_id": context.correlation_id,
            "duration_ms": duration,
            "simulation": simulate,
        }


engine = ToolDiscoveryEngine()
