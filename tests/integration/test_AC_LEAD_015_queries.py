"""Lead query and batch report tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _import_mock(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/lead-batches/import", json={"source": "mock"}
    )
    assert response.status_code == 201
    return response.json()


def test_AC_LEAD_015_lead_filters_and_pagination(client: TestClient) -> None:
    """Given imported leads, when filtered and paged, then results match the filters."""
    batch = _import_mock(client)
    assert client.get("/api/v1/leads", params={"status": "NEW"}).json()["total"] == 44
    assert client.get("/api/v1/leads", params={"min_score": 50}).json()["total"] == 0
    assert (
        client.get("/api/v1/leads", params={"batch_id": batch["id"]}).json()["total"]
        == 44
    )

    matched = client.get("/api/v1/leads", params={"q": "glow"}).json()
    assert matched["total"] > 0
    for item in matched["items"]:
        haystack = " ".join(
            filter(None, [item["username"], item["display_name"], item["bio"]])
        )
        assert "glow" in haystack.lower()

    english = client.get("/api/v1/leads", params={"language": "en"}).json()
    assert english["total"] > 0
    assert all(item["language"] == "en" for item in english["items"])

    region = client.get("/api/v1/leads", params={"region": "us"}).json()
    assert region["total"] > 0
    assert all(item["region"] == "US" for item in region["items"])

    page = client.get(
        "/api/v1/leads", params={"page": 2, "page_size": 10}
    ).json()
    assert (len(page["items"]), page["total"], page["page"]) == (10, 44, 2)


def test_AC_LEAD_015_q_treats_like_wildcards_literally(client: TestClient) -> None:
    """Given q containing a LIKE wildcard, when filtered, then it matches literal text only."""
    _import_mock(client)
    assert client.get("/api/v1/leads", params={"q": "glow%"}).json()["total"] == 0
    assert client.get("/api/v1/leads", params={"q": "glow"}).json()["total"] > 0


def test_AC_LEAD_015_batch_detail_and_lead_detail_are_safe(client: TestClient) -> None:
    """Given a batch, when read back, then the full report and masked lead are returned."""
    batch = _import_mock(client)
    detail = client.get(f"/api/v1/lead-batches/{batch['id']}").json()
    assert detail["total_rows"] == 52
    assert detail["imported"] == 44
    assert len(detail["errors"]) == 9
    assert detail["created_by"] == "admin"

    lead_id = client.get("/api/v1/leads").json()["items"][0]["id"]
    lead = client.get(f"/api/v1/leads/{lead_id}").json()
    assert lead["phone_masked"] is None or "****" in lead["phone_masked"]
    assert "phone_enc" not in lead
    assert "phone_hash" not in lead
    assert client.get("/api/v1/lead-batches/9999").status_code == 404
    assert client.get("/api/v1/leads/9999").status_code == 404
