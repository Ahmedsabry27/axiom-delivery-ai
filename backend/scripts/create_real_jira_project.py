"""Create the approved AI Delivery Platform project in the configured Jira Cloud site."""

from __future__ import annotations

import httpx

from app.database.models.integration import IntegrationConnection
from app.database.session import SessionLocal
from app.integrations.secrets import secret_provider


def main() -> None:
    db = SessionLocal()
    try:
        connection = db.query(IntegrationConnection).filter_by(
            tenant_id="axiom-demo", connector_type="jira"
        ).one()
        credential = secret_provider.resolve(connection.secret_ref)
        with httpx.Client(
            base_url=connection.base_url,
            auth=(credential["email"], credential["api_token"]),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30,
            follow_redirects=False,
        ) as client:
            existing = client.get("/rest/api/3/project/AIDP")
            if existing.status_code == 200:
                project = existing.json()
                print(f"Project already exists: {project['key']} | {project['name']} | {connection.base_url}/browse/{project['key']}")
                return
            profile = client.get("/rest/api/3/myself")
            profile.raise_for_status()
            response = client.post(
                "/rest/api/3/project",
                json={
                    "key": "AIDP",
                    "name": "AI Delivery Platform",
                    "projectTypeKey": "software",
                    "projectTemplateKey": "com.pyxis.greenhopper.jira:gh-kanban-template",
                    "description": "Delivery planning and execution for the AI Delivery Platform.",
                    "leadAccountId": profile.json()["accountId"],
                    "assigneeType": "PROJECT_LEAD",
                },
            )
            if response.status_code != 201:
                detail = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                messages = detail.get("errorMessages") or list((detail.get("errors") or {}).values())
                raise SystemExit(f"Jira project creation failed ({response.status_code}): {'; '.join(map(str, messages)) or 'Provider rejected the request'}")
            project = response.json()
            print(f"Created project: {project['key']} | AI Delivery Platform | {connection.base_url}/browse/{project['key']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
