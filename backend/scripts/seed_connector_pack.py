"""Populate AX-EP12A deterministic connector records through the API service boundary."""

from app.api.integrations import SyncPayload, synchronize
from app.database.models.integration import IntegrationConnection
from app.database.session import SessionLocal

USER = {
    "sub": "AX-EP12A",
    "custom:tenant_id": "axiom-demo",
    "cognito:groups": ["admin"],
}
TARGETS = {
    "jira": ("Axiom Jira Demo", "https://api.atlassian.com", "atlassian"),
    "confluence": ("Axiom Confluence Demo", "https://api.atlassian.com", "atlassian"),
    "outlook_calendar": (
        "Axiom Outlook Demo",
        "https://graph.microsoft.com",
        "microsoft",
    ),
    "microsoft_teams": ("Axiom Teams Demo", "https://graph.microsoft.com", "microsoft"),
}


def main() -> None:
    db = SessionLocal()
    try:
        legacy = {"outlook": "outlook_calendar", "teams": "microsoft_teams"}
        for old, new in legacy.items():
            row = (
                db.query(IntegrationConnection)
                .filter_by(tenant_id="axiom-demo", connector_type=old)
                .first()
            )
            if row:
                row.connector_type = new
        db.commit()
        for connector_type, (name, base_url, provider) in TARGETS.items():
            row = (
                db.query(IntegrationConnection)
                .filter_by(tenant_id="axiom-demo", connector_type=connector_type)
                .first()
            )
            if not row:
                row = IntegrationConnection(
                    tenant_id="axiom-demo",
                    connector_type=connector_type,
                    name=f"axiom-{connector_type}-demo",
                    display_name=name,
                    description="Deterministic AX-EP12A simulator connection",
                    auth_type="oauth2",
                    status="CONFIGURATION_REQUIRED",
                    health_status="not_configured",
                    base_url=base_url,
                    created_by="AX-EP12A",
                    enabled=False,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
            row.display_name = name
            row.auth_type = "oauth2"
            row.base_url = base_url
            row.secret_ref = f"simulator://oauth/axiom-{provider}-demo"
            row.configuration = {
                **(row.configuration or {}),
                "simulator": True,
                "provider_tenant_id": f"axiom-{provider}-demo",
                "source_scope": {"selection": "Authorized demo sources"},
            }
            row.safe_metadata = {
                **(row.safe_metadata or {}),
                "mode": "SIMULATOR",
                "simulated": True,
            }
            db.commit()
            synchronize(row.id, SyncPayload(mode="FULL", trigger="MANUAL"), db, USER)
            print(f"{connector_type}: synchronized")
    finally:
        db.close()


if __name__ == "__main__":
    main()
