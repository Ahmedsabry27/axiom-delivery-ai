from fastapi import HTTPException

from app.api.settings import Patch, resolve, write_category

ADMIN = {
    "sub": "admin-a",
    "custom:tenant_id": "tenant-a",
    "cognito:groups": ["workspace-admin"],
}
USER = {"sub": "user-a", "custom:tenant_id": "tenant-a", "cognito:groups": []}


def item(items, key):
    return next(value for value in items if value["key"] == key)


def test_effective_precedence_and_user_isolation(db_session):
    write_category(
        "workspace",
        Patch(values={"workspace.primary_timezone": "Europe/London"}),
        db_session,
        ADMIN,
    )
    inherited = item(
        resolve(db_session, USER, "workspace"), "workspace.primary_timezone"
    )
    assert inherited["effective_value"] == "Europe/London"
    assert inherited["source_scope"] == "tenant"
    write_category(
        "profile",
        Patch(values={"profile.display_timezone": "Africa/Cairo"}),
        db_session,
        USER,
    )
    personal = item(resolve(db_session, USER, "profile"), "profile.display_timezone")
    other = item(resolve(db_session, ADMIN, "profile"), "profile.display_timezone")
    assert personal["effective_value"] == "Africa/Cairo"
    assert other["effective_value"] == "UTC"


def test_unknown_locked_and_invalid_values_fail(db_session):
    for payload in (
        Patch(values={"production.mocks": True}),
        Patch(values={"data.audit_retention": "Disabled"}),
        Patch(values={"preferences.page_size": 0}),
    ):
        try:
            write_category(
                "preferences" if "preferences.page_size" in payload.values else "data",
                payload,
                db_session,
                USER,
            )
        except HTTPException as exc:
            assert exc.status_code in {403, 405, 422}
        else:
            raise AssertionError("Unsafe or invalid setting was accepted")


def test_workspace_authorization_and_optimistic_concurrency(db_session):
    try:
        write_category(
            "workspace",
            Patch(values={"workspace.display_name": "No"}),
            db_session,
            USER,
        )
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Normal user edited workspace settings")
    write_category(
        "workspace",
        Patch(values={"workspace.display_name": "Axiom Demo"}),
        db_session,
        ADMIN,
    )
    try:
        write_category(
            "workspace",
            Patch(
                values={"workspace.display_name": "Stale"},
                expected_versions={"workspace.display_name": 0},
            ),
            db_session,
            ADMIN,
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("Stale setting write was accepted")
