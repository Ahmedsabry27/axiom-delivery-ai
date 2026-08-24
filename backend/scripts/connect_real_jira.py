"""Securely configure and verify the local Jira Cloud connector."""

from __future__ import annotations

import getpass
import json
import subprocess

import httpx

from app.database.models.integration import IntegrationConnection
from app.database.session import SessionLocal

SITE = "https://ahmedsabry27.atlassian.net"
EMAIL = "ahmedsabry27@outlook.com"
SERVICE = "axiom.ai-delivery-platform.jira.ahmedsabry27"


def main() -> None:
    token = getpass.getpass("New Atlassian API token (hidden): ").strip()
    if len(token) < 20:
        raise SystemExit("Token was empty or unexpectedly short; nothing changed.")
    response = httpx.get(
        f"{SITE}/rest/api/3/myself",
        auth=(EMAIL, token),
        headers={"Accept": "application/json"},
        timeout=20,
        follow_redirects=False,
    )
    if response.status_code != 200:
        raise SystemExit(
            f"Jira verification failed with HTTP {response.status_code}; nothing changed."
        )
    payload = json.dumps({"email": EMAIL, "api_token": token})
    subprocess.run(
        [
            "security",
            "add-generic-password",
            "-U",
            "-a",
            EMAIL,
            "-s",
            SERVICE,
            "-w",
            payload,
        ],
        check=True,
        capture_output=True,
        timeout=10,
    )
    token = payload = ""
    db = SessionLocal()
    try:
        row = (
            db.query(IntegrationConnection)
            .filter_by(tenant_id="axiom-demo", connector_type="jira")
            .first()
        )
        if not row:
            raise SystemExit("The Jira connector row does not exist.")
        row.display_name = "Ahmed Sabry Jira Cloud"
        row.base_url = SITE
        row.auth_type = "api_token"
        row.secret_ref = f"keychain://{SERVICE}"
        row.configuration = {
            **(row.configuration or {}),
            "simulator": False,
            "site_url": SITE,
        }
        row.safe_metadata = {
            "mode": "LIVE",
            "account": response.json().get("displayName", EMAIL),
            "site": SITE,
        }
        row.status = "CONNECTED"
        row.health_status = "healthy"
        row.enabled = True
        row.last_error_code = row.last_error_message_safe = None
        db.commit()
    finally:
        db.close()
    print(
        "Jira verified and connected. The token is stored in macOS Keychain; "
        "PostgreSQL contains only its reference."
    )


if __name__ == "__main__":
    main()
