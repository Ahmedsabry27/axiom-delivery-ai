"""Assign Axiom Jira delivery stories to the connected Jira account."""
from __future__ import annotations

import httpx

from app.database.models.integration import IntegrationConnection
from app.database.session import SessionLocal
from app.integrations.secrets import secret_provider


def require(response: httpx.Response, operation: str, accepted=(200, 204)) -> dict:
    if response.status_code not in accepted:
        try:
            body = response.json()
            errors = body.get("errorMessages") or list((body.get("errors") or {}).values())
        except ValueError:
            errors = []
        raise RuntimeError(f"{operation} failed ({response.status_code}): {'; '.join(map(str, errors)) or 'Provider rejected request'}")
    return response.json() if response.content else {}


def main() -> None:
    db = SessionLocal()
    try:
        connection = db.query(IntegrationConnection).filter_by(tenant_id="axiom-demo", connector_type="jira").one()
        credential = secret_provider.resolve(connection.secret_ref)
        with httpx.Client(base_url=connection.base_url, auth=(credential["email"], credential["api_token"]), headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=30) as client:
            me = require(client.get("/rest/api/3/myself"), "Account lookup")
            result = require(client.get("/rest/api/3/search/jql", params={
                "jql": 'labels = "axiom-real-portfolio" AND issuetype != Epic ORDER BY created ASC',
                "fields": "assignee,status",
                "maxResults": 100,
            }), "Delivery work lookup")
            changed = 0
            for issue in result.get("issues", []):
                assignee = issue.get("fields", {}).get("assignee") or {}
                if assignee.get("accountId") == me["accountId"]:
                    continue
                require(client.put(f"/rest/api/3/issue/{issue['key']}", json={"fields": {"assignee": {"accountId": me["accountId"]}}}), f"Assign {issue['key']}")
                changed += 1
            print(f"Jira work assignment ready: {len(result.get('issues', []))} stories owned by {me.get('displayName')}; {changed} updated.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
