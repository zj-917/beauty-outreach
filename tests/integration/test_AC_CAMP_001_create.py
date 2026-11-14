"""Campaign creation, target snapshot and audit tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import Lead, TaskItem
from app.services.seed_service import seed_defaults


def _prepare(client: TestClient, db: Engine, clock: FakeClock) -> int:
    """Seed defaults, import the mock batch, screen it and return the approved template id."""
    with Session(db) as session:
        seed_defaults(session, clock)
    assert client.post("/api/v1/lead-batches/import", json={"source": "mock"}).status_code == 201
    assert client.post("/api/v1/leads/screen").status_code == 200
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


def _create(client: TestClient, template_id: int, selection: dict | None = None) -> dict:
    """Create one campaign and return the raw JSON body."""
    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "first wave",
            "template_id": template_id,
            "selection": selection or {},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_AC_CAMP_001_create_snapshots_targets_and_audits(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given an approved template and pool, when creating, then DRAFT and PENDING items appear."""
    template_id = _prepare(client, db, clock)

    body = _create(client, template_id)

    assert body["status"] == "DRAFT"
    assert body["template_id"] == template_id
    assert body["total_items"] == 20
    assert body["counts"]["in_progress"] == 20
    items = client.get(
        f"/api/v1/campaigns/{body['id']}/items", params={"page_size": 100}
    ).json()
    assert items["total"] == 20
    assert {item["status"] for item in items["items"]} == {"PENDING"}

    with Session(db) as session:
        rows = session.scalars(
            select(TaskItem).where(TaskItem.task_id == body["id"])
        ).all()
        assert len(rows) == 20
        leads = {
            lead.id: lead
            for lead in session.scalars(
                select(Lead).where(Lead.id.in_({row.lead_id for row in rows}))
            ).all()
        }
        for row in rows:
            assert row.phone_hash == leads[row.lead_id].phone_hash
            assert row.phone_masked == leads[row.lead_id].phone_masked
        assert any(row.phone_masked for row in rows)
        assert len({row.idempotency_key for row in rows}) == 20

    audit = client.get(
        "/api/v1/audit-logs",
        params={"action": "CAMPAIGN_CREATED", "entity_id": str(body["id"])},
    ).json()
    assert audit["total"] == 1
    record = audit["items"][0]
    assert record["before"] is None
    assert record["after"]["status"] == "DRAFT"
    assert record["after"]["total_items"] == 20
    assert "selection" in record["after"]


def test_AC_CAMP_001_selection_conditions_take_intersection(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given three filters, when creating, then items equal their intersection."""
    template_id = _prepare(client, db, clock)
    pool = client.get("/api/v1/pool", params={"page_size": 100}).json()["items"]
    lead_ids = [item["id"] for item in pool[:8]]
    min_score = pool[4]["score"]
    expected = {
        item["id"] for item in pool[:8] if item["score"] is not None and item["score"] >= min_score
    }
    assert 0 < len(expected) <= 8

    body = _create(
        client,
        template_id,
        {"min_score": min_score, "batch_id": 1, "lead_ids": lead_ids},
    )

    assert body["total_items"] == len(expected)
    items = client.get(
        f"/api/v1/campaigns/{body['id']}/items", params={"page_size": 100}
    ).json()["items"]
    assert {item["lead_id"] for item in items} == expected


def test_AC_CAMP_001_empty_target_is_rejected_without_side_effects(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a filter matching no approved lead, when creating, then 422 and nothing is stored."""
    template_id = _prepare(client, db, clock)

    response = client.post(
        "/api/v1/campaigns",
        json={
            "name": "no targets",
            "template_id": template_id,
            "selection": {"lead_ids": [999_999]},
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CAMPAIGN_EMPTY_TARGET"
    assert client.get("/api/v1/campaigns").json()["total"] == 0
    audit = client.get(
        "/api/v1/audit-logs", params={"action": "CAMPAIGN_CREATED"}
    ).json()
    assert audit["total"] == 0


def test_AC_CAMP_001_template_must_be_approved(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given a draft or missing template, when creating, then 422 TEMPLATE_NOT_APPROVED or 404."""
    _prepare(client, db, clock)
    draft = client.post(
        "/api/v1/templates",
        json={"name": "draft-only", "body": "Hi {{name}}", "language": "en"},
    ).json()

    response = client.post(
        "/api/v1/campaigns",
        json={"name": "draft template", "template_id": draft["id"]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TEMPLATE_NOT_APPROVED"
    missing = client.post(
        "/api/v1/campaigns", json={"name": "missing template", "template_id": 999_999}
    )
    assert missing.status_code == 404
