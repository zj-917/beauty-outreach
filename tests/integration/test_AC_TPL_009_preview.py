"""Template preview tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.models import SendLog


def _create(client: TestClient, *, body: str, name: str = "welcome"):
    return client.post(
        "/api/v1/templates",
        json={"name": name, "body": body, "language": "en"},
    )


def test_AC_TPL_009_preview_body_with_example_lead(
    client: TestClient,
) -> None:
    """Given only a body, when previewed, then the built-in example lead is rendered."""
    response = client.post(
        "/api/v1/templates/preview",
        json={"body": "Hi {{name}} from {{brand}}. {{optout_text}}"},
    )

    assert response.status_code == 200
    rendered = response.json()["rendered"]
    assert rendered.startswith("Hi Alex from GlowLab.")
    assert "Reply STOP" in rendered


def test_AC_TPL_009_preview_template_with_lead(client: TestClient) -> None:
    """Given a draft template and lead id, when previewed, then the lead is rendered."""
    assert (
        client.post(
            "/api/v1/lead-batches/import", json={"source": "mock"}
        ).status_code
        == 201
    )
    lead = client.get("/api/v1/leads").json()["items"][0]
    template_id = _create(client, body="Hi {{name}}").json()["id"]

    response = client.post(
        "/api/v1/templates/preview",
        json={"template_id": template_id, "lead_id": lead["id"]},
    )

    assert response.status_code == 200
    rendered = response.json()["rendered"]
    expected_name = lead["display_name"] or lead["username"]
    assert rendered.startswith(f"Hi {expected_name}")
    assert rendered.endswith(
        "\n\nReply STOP to unsubscribe. 回复 STOP 退订。"
    )


def test_AC_TPL_009_preview_has_no_side_effects(
    client: TestClient, db: Engine
) -> None:
    """Given a preview, when rendered, then audit, send_log and Messenger are untouched."""
    assert (
        client.post(
            "/api/v1/lead-batches/import", json={"source": "mock"}
        ).status_code
        == 201
    )
    before_audit = client.get("/api/v1/audit-logs").json()["total"]
    with Session(db) as session:
        before_send = session.scalar(select(func.count()).select_from(SendLog)) or 0

    response = client.post(
        "/api/v1/templates/preview", json={"body": "Hi {{name}}"}
    )

    assert response.status_code == 200
    after_audit = client.get("/api/v1/audit-logs").json()["total"]
    with Session(db) as session:
        after_send = session.scalar(select(func.count()).select_from(SendLog)) or 0
    assert after_audit == before_audit
    assert after_send == before_send == 0
    assert client.app.state.messenger is None


def test_AC_TPL_009_preview_requires_body_or_template(
    client: TestClient,
) -> None:
    """Given neither body nor template_id, when previewed, then 422 is returned."""
    response = client.post("/api/v1/templates/preview", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_AC_TPL_009_preview_reports_missing_references(
    client: TestClient,
) -> None:
    """Given an unknown template or lead id, when previewed, then 404 is returned."""
    assert (
        client.post(
            "/api/v1/templates/preview", json={"template_id": 9999}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/templates/preview",
            json={"body": "Hi {{name}}", "lead_id": 9999},
        ).status_code
        == 404
    )


def test_AC_TPL_009_preview_maps_render_failures(
    client: TestClient,
) -> None:
    """Given an unknown variable or a missing keyword, when previewed, then 422 explains why."""
    unknown = client.post(
        "/api/v1/templates/preview", json={"body": "Hi {{phone}}"}
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "TEMPLATE_UNKNOWN_VARIABLE"

    assert (
        client.post(
            "/api/v1/lead-batches/import", json={"source": "mock"}
        ).status_code
        == 201
    )
    lead = client.get("/api/v1/leads").json()["items"][0]
    missing = client.post(
        "/api/v1/templates/preview",
        json={"body": "About {{keyword}}", "lead_id": lead["id"]},
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "VALIDATION_ERROR"
    assert missing.json()["error"]["details"]["reason"] == "TEMPLATE_VARIABLE_MISSING"
