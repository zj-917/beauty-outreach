"""Start precondition tests (CAMP-027) and provider gating."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.core.config import Settings
from app.main import create_app
from app.models import TaskItem
from app.services.seed_service import seed_defaults


def _prepare(client: TestClient, db: Engine, clock: FakeClock) -> int:
    """Seed defaults, import the mock batch, screen it and return the approved template id."""
    with Session(db) as session:
        seed_defaults(session, clock)
    assert client.post("/api/v1/lead-batches/import", json={"source": "mock"}).status_code == 201
    assert client.post("/api/v1/leads/screen").status_code == 200
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


def _create(client: TestClient, template_id: int) -> int:
    response = client.post(
        "/api/v1/campaigns",
        json={"name": "preconditions", "template_id": template_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _status(client: TestClient, campaign_id: int) -> str:
    return client.get(f"/api/v1/campaigns/{campaign_id}").json()["status"]


def test_AC_CAMP_027_disabled_template_blocks_start(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given the template is disabled after creation, when starting, then 422 and DRAFT stays."""
    template_id = _prepare(client, db, clock)
    campaign_id = _create(client, template_id)
    assert client.post(f"/api/v1/templates/{template_id}/disable").status_code == 200

    response = client.post(f"/api/v1/campaigns/{campaign_id}/start")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TEMPLATE_NOT_APPROVED"
    assert _status(client, campaign_id) == "DRAFT"


def test_AC_CAMP_027_no_open_items_blocks_start(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given every item is terminal, when starting, then 422 CAMPAIGN_EMPTY_TARGET."""
    template_id = _prepare(client, db, clock)
    campaign_id = _create(client, template_id)
    with Session(db) as session:
        rows = session.scalars(
            select(TaskItem).where(TaskItem.task_id == campaign_id)
        ).all()
        for row in rows:
            row.status = "SKIPPED"
            row.reason_code = "TASK_CANCELLED"
        session.commit()

    response = client.post(f"/api/v1/campaigns/{campaign_id}/start")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CAMPAIGN_EMPTY_TARGET"
    assert _status(client, campaign_id) == "DRAFT"


def test_AC_CAMP_027_cloud_provider_blocks_start_with_501(
    client: TestClient, db: Engine, clock: FakeClock, settings: Settings
) -> None:
    """Given MESSENGER_PROVIDER=whatsapp_cloud, when starting, then 501 and DRAFT stays."""
    cloud_settings = settings.model_copy(update={"messenger_provider": "whatsapp_cloud"})
    cloud_app = create_app(settings=cloud_settings, clock=clock)
    with TestClient(
        cloud_app, headers={"X-Admin-Token": settings.admin_token}
    ) as cloud_client:
        template_id = _prepare(cloud_client, db, clock)
        campaign_id = _create(cloud_client, template_id)

        response = cloud_client.post(f"/api/v1/campaigns/{campaign_id}/start")

        assert response.status_code == 501
        assert response.json()["error"]["code"] == "PROVIDER_NOT_ENABLED"
        assert _status(cloud_client, campaign_id) == "DRAFT"


def test_AC_CAMP_027_checks_run_in_the_documented_order(
    client: TestClient, db: Engine, clock: FakeClock, settings: Settings
) -> None:
    """Given all three preconditions fail, when starting, then the template error wins."""
    cloud_settings = settings.model_copy(update={"messenger_provider": "whatsapp_cloud"})
    cloud_app = create_app(settings=cloud_settings, clock=clock)
    with TestClient(
        cloud_app, headers={"X-Admin-Token": settings.admin_token}
    ) as cloud_client:
        template_id = _prepare(cloud_client, db, clock)
        campaign_id = _create(cloud_client, template_id)
        with Session(db) as session:
            rows = session.scalars(
                select(TaskItem).where(TaskItem.task_id == campaign_id)
            ).all()
            for row in rows:
                row.status = "SKIPPED"
                row.reason_code = "TASK_CANCELLED"
            session.commit()
        assert (
            cloud_client.post(f"/api/v1/templates/{template_id}/disable").status_code
            == 200
        )

        response = cloud_client.post(f"/api/v1/campaigns/{campaign_id}/start")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TEMPLATE_NOT_APPROVED"
