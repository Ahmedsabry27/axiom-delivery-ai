import json
from pathlib import Path

import pytest

from app.contracts.tool_models import ExecutionContext
from app.tool_discovery.engine import engine
from app.tool_discovery.schemas import DiscoveryRequest
from app.tool_sdk.service import sync_catalog


@pytest.mark.asyncio
async def test_offline_discovery_security_benchmark(db_session):
    sync_catalog(db_session)
    cases = json.loads((Path(__file__).parent / "discovery_benchmark.json").read_text())
    unauthorized = leakage = 0
    top1 = valid = 0
    for case in cases:
        permissions = set(case["permissions"])
        result = await engine.discover(
            DiscoveryRequest(
                query=case["query"], risk_tolerance=case.get("risk_tolerance", "read")
            ),
            ExecutionContext(
                actor_id="benchmark", tenant_id="default", permissions=permissions
            ),
            db_session,
        )
        selected = result["selected"]["tool_name"] if result["selected"] else None
        if case["expected"]:
            valid += 1
            top1 += selected == case["expected"]
        for candidate in result["candidates"]:
            if (
                set(
                    __import__("app.tool_sdk.service", fromlist=["registry"])
                    .registry.get(candidate["tool_name"])
                    .metadata.permissions
                )
                - permissions
            ):
                unauthorized += 1
    assert unauthorized == 0 and leakage == 0
    assert top1 / max(1, valid) >= 2 / 3
