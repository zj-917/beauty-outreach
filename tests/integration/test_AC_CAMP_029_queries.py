"""Campaign list, detail and item query tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.clock import FakeClock
from app.models import TaskItem
from app.services.seed_service import seed_defaults

_MIX = (
    ["SENT"] * 3
    + ["DELIVERED"] * 2
    + ["READ"] * 1
    + ["FAILED"] * 2
    + ["SKIPPED"] * 3
    + ["RETRY_WAIT"] * 1
)


def _prepare(client: TestClient, db: Engine, clock: FakeClock) -> int:
    """Seed defaults, import the mock batch, screen it and return the approved template id."""
    with Session(db) as session:
        seed_defaults(session, clock)
    assert client.post("/api/v1/lead-batches/import", json={"source": "mock"}).status_code == 201
    assert client.post("/api/v1/leads/screen").status_code == 200
    templates = client.get("/api/v1/templates").json()
    return next(item["id"] for item in templates if item["name"] == "greeting")


def _create(client: TestClient, template_id: int, name: str) -> int:
    response = client.post(
        "/api/v1/campaigns", json={"name": name, "template_id": template_id}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _mix_statuses(db: Engine, campaign_id: int) -> None:
    """Write a deterministic mix of item statuses and reason codes."""
    with Session(db) as session:
        rows = session.scalars(
            select(TaskItem)
            .where(TaskItem.task_id == campaign_id)
            .order_by(TaskItem.id)
        ).all()
        for row, status in zip(rows, _MIX, strict=False):
            row.status = status
            if status == "FAILED":
                row.reason_code = "MAX_ATTEMPTS_EXCEEDED"
            elif status == "SKIPPED":
                row.reason_code = "NO_CONSENT"
        session.commit()


def test_AC_CAMP_029_list_and_detail_carry_summary_counts(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given two tasks, when listed and read, then summary counts match the item mix."""
    template_id = _prepare(client, db, clock)
    first = _create(client, template_id, "first")
    second = _create(client, template_id, "second")
    _mix_statuses(db, first)

    listing = client.get("/api/v1/campaigns").json()

    assert listing["total"] == 2
    assert [item["id"] for item in listing["items"]] == [second, first]
    summary = next(item for item in listing["items"] if item["id"] == first)
    assert summary["total_items"] == 20
    assert summary["counts"]["total"] == 20
    assert summary["counts"]["success"] == 6
    assert summary["counts"]["failed"] == 2
    assert summary["counts"]["skipped"] == 3
    assert summary["counts"]["in_progress"] == 9
    assert summary["counts"]["by_status"]["DELIVERED"] == 2
    assert summary["counts"]["by_status"]["PENDING"] == 8

    detail = client.get(f"/api/v1/campaigns/{first}").json()
    assert detail["counts"] == summary["counts"]
    assert detail["selection"] == {"min_score": None, "batch_id": None, "lead_ids": None}
    assert detail["template_id"] == template_id
    assert detail["created_at"] == "2026-11-14T09:00:00Z"

    page = client.get("/api/v1/campaigns", params={"page": 2, "page_size": 1}).json()
    assert page["total"] == 2
    assert [item["id"] for item in page["items"]] == [first]


def test_AC_CAMP_029_items_support_status_reason_and_text_filters(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given mixed items, when filtered and paged, then only matching masked rows return."""
    template_id = _prepare(client, db, clock)
    campaign_id = _create(client, template_id, "filtered")
    _mix_statuses(db, campaign_id)

    skipped = client.get(
        f"/api/v1/campaigns/{campaign_id}/items",
        params={"status": "SKIPPED", "page_size": 100},
    ).json()
    assert skipped["total"] == 3
    assert {(item["status"], item["reason_code"]) for item in skipped["items"]} == {
        ("SKIPPED", "NO_CONSENT")
    }

    by_reason = client.get(
        f"/api/v1/campaigns/{campaign_id}/items",
        params={"reason_code": "MAX_ATTEMPTS_EXCEEDED", "page_size": 100},
    ).json()
    assert by_reason["total"] == 2
    assert {item["status"] for item in by_reason["items"]} == {"FAILED"}

    sample = by_reason["items"][0]
    by_text = client.get(
        f"/api/v1/campaigns/{campaign_id}/items",
        params={"q": sample["lead_username"], "page_size": 100},
    ).json()
    assert by_text["total"] == 1
    assert by_text["items"][0]["lead_username"] == sample["lead_username"]

    pages = [
        client.get(
            f"/api/v1/campaigns/{campaign_id}/items",
            params={"page": page, "page_size": 7},
        ).json()
        for page in (1, 2, 3)
    ]
    assert [page["total"] for page in pages] == [20, 20, 20]
    assert [len(page["items"]) for page in pages] == [7, 7, 6]

    for item in pages[0]["items"]:
        assert "phone_masked" in item
        assert "phone_hash" not in item
        assert "phone_enc" not in item
        assert "rendered_body" not in item


def test_AC_CAMP_029_unknown_campaign_is_404(
    client: TestClient, db: Engine, clock: FakeClock
) -> None:
    """Given no such task, when read, then detail and items return 404."""
    _prepare(client, db, clock)

    assert client.get("/api/v1/campaigns/999").status_code == 404
    assert client.get("/api/v1/campaigns/999/items").status_code == 404
    assert client.post("/api/v1/campaigns/999/start").status_code == 404
