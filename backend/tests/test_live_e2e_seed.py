from __future__ import annotations

import json

from app.auth.e2e import verify_e2e_token
from scripts.seed_live_e2e import main


def test_seed_writes_restricted_signed_tenant_state(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    monkeypatch.setenv("APP_ENV", "e2e")
    monkeypatch.setenv("E2E_AUTH_ENABLED", "true")
    monkeypatch.setenv("E2E_AUTH_SECRET", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("E2E_STATE_PATH", str(state_path))

    main()

    state = json.loads(state_path.read_text())
    assert set(state) == {
        "token",
        "cross_tenant_token",
        "tenant",
        "actor",
        "agent_id",
        "sprint_id",
        "work_item_id",
        "dependency_id",
        "evidence_id",
        "recommendation_id",
        "raid_id",
        "candidate_id",
        "project_id",
        "milestone_id",
        "release_id",
        "requester_token",
        "approver_token",
        "executor_token",
        "verifier_token",
        "requester_id",
        "approver_id",
        "executor_id",
        "verifier_id",
        "expired_approval_id",
        "stale_approval_id",
    }
    assert state_path.stat().st_mode & 0o777 == 0o600
    owner = verify_e2e_token(state["token"])
    outsider = verify_e2e_token(state["cross_tenant_token"])
    assert owner["custom:tenant_id"] == state["tenant"]
    assert owner["sub"] == state["actor"]
    assert outsider["custom:tenant_id"] != state["tenant"]
    for role in ("requester", "approver", "executor", "verifier"):
        claims = verify_e2e_token(state[f"{role}_token"])
        assert claims["custom:tenant_id"] == state["tenant"]
        assert claims["sub"] == state[f"{role}_id"]
