"""Target snapshot semantics tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
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
        json={"name": "snapshot", "template_id": template_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_AC_CAMP_002_pool_changes_leave_existing_items_untouched(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a created task, when the pool changes, then its item set stays identical."""
    template_id = _prepare(client, db, clock)
    campaign_id = _create(client, template_id)
    before = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()
    original = {item["lead_id"] for item in before["items"]}
    assert len(original) == 20

    removed = list(original)[:2]
    for lead_id in removed:
        response = client.post(
            f"/api/v1/leads/{lead_id}/review",
            json={"decision": "REJECT", "note": "snapshot test"},
        )
        assert response.status_code == 200
    discarded = client.get("/api/v1/leads", params={"status": "DISCARDED"}).json()["items"]
    restored = client.post(
        f"/api/v1/leads/{discarded[0]['id']}/review",
        json={"decision": "APPROVE", "note": "back in pool"},
    )
    assert restored.status_code == 200

    pool_total = client.get("/api/v1/pool").json()["total"]
    assert pool_total == 19

    after = client.get(
        f"/api/v1/campaigns/{campaign_id}/items", params={"page_size": 100}
    ).json()
    assert after["total"] == 20
    assert {item["lead_id"] for item in after["items"]} == original
    assert {item["status"] for item in after["items"]} == {"PENDING"}


def test_AC_CAMP_002_later_campaigns_see_the_current_pool(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given pool changes, when creating another task, then it snapshots the new membership."""
    template_id = _prepare(client, db, clock)
    first = client.get(
        f"/api/v1/campaigns/{_create(client, template_id)}/items",
        params={"page_size": 100},
    ).json()
    removed = {item["lead_id"] for item in first["items"][:2]}
    for lead_id in removed:
        assert (
            client.post(
                f"/api/v1/leads/{lead_id}/review",
                json={"decision": "REJECT", "note": "left the pool"},
            ).status_code
            == 200
        )

    second_id = _create(client, template_id)
    second = client.get(
        f"/api/v1/campaigns/{second_id}/items", params={"page_size": 100}
    ).json()

    assert second["total"] == 18
    assert removed.isdisjoint({item["lead_id"] for item in second["items"]})
