"""Duplicate, merge and conflict handling tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

HEADER = (
    "username,display_name,bio,region,language,source_url,phone,"
    "consent_status,consent_source,consent_evidence\n"
)


def _import(client: TestClient, rows: str) -> dict:
    response = client.post(
        "/api/v1/lead-batches/import",
        files={"file": ("dup.csv", (HEADER + rows).encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 201
    return response.json()


def _lead(client: TestClient, query: str) -> dict:
    items = client.get("/api/v1/leads", params={"q": query}).json()["items"]
    assert len(items) == 1
    return items[0]


def test_AC_LEAD_005_duplicates_fill_empty_fields_only(client: TestClient) -> None:
    """Given a repeated username, when imported, then no new lead is created and gaps are filled."""
    first = _import(client, "merge.me,,,,,,+15555550121,,,\n")
    assert first["imported"] == 1
    second = _import(
        client,
        "MERGE.ME,New Name,New bio,GB,en,https://instagram.com/x,,,,\n",
    )
    assert (second["imported"], second["duplicates"]) == (0, 1)
    assert second["errors"][0]["code"] == "DUPLICATE_USERNAME"
    lead = _lead(client, "merge.me")
    assert lead["display_name"] == "New Name"
    assert lead["bio"] == "New bio"
    assert lead["region"] == "GB"

    third = _import(client, "merge.me,Other,Other bio,,,,\n")
    assert third["duplicates"] == 1
    lead = _lead(client, "merge.me")
    assert (lead["display_name"], lead["bio"], lead["region"]) == (
        "New Name",
        "New bio",
        "GB",
    )
    assert client.get("/api/v1/leads").json()["total"] == 1


def test_AC_LEAD_005_duplicate_phone_and_within_batch_duplicates(
    client: TestClient,
) -> None:
    """Given a phone already used or a repeated username in one file, then duplicates count."""
    _import(client, "taken.phone,,,,,,+15555550122,,,\n")
    body = _import(
        client,
        "other.user,,,,,,+15555550122,,,\n"
        "batch.dup,,,,,,+15555550123,,,\n"
        "BATCH.DUP,,,,,,,,,\n",
    )
    assert (body["imported"], body["duplicates"]) == (1, 2)
    codes = [item["code"] for item in body["errors"]]
    assert codes == ["DUPLICATE_PHONE", "DUPLICATE_USERNAME"]
    assert client.get("/api/v1/leads").json()["total"] == 2


def test_AC_LEAD_006_conflicting_phone_keeps_original(client: TestClient) -> None:
    """Given a known username with another phone, then IMPORT_CONFLICT keeps the first phone."""
    _import(client, "conflict.user,,,,,,+15555550131,,,\n")
    body = _import(client, "conflict.user,,,,,,+15555550132,,,\n")
    assert (body["imported"], body["duplicates"]) == (0, 1)
    assert body["errors"][0]["code"] == "IMPORT_CONFLICT"
    lead = _lead(client, "conflict.user")
    assert lead["phone_masked"] == "+155****0131"


def test_AC_LEAD_005_merge_never_steals_another_leads_phone(
    client: TestClient,
) -> None:
    """Given a phone owned by another lead, when merging, then it is not copied."""
    _import(client, "no.phone.lead,,,,,,,,\n" + "owner.lead,,,,,,+15555550161,,,\n")
    body = _import(client, "no.phone.lead,,,,,,+15555550161,,,\n")
    assert (body["imported"], body["duplicates"]) == (0, 1)
    assert body["errors"][0]["code"] == "IMPORT_CONFLICT"
    without_phone = _lead(client, "no.phone.lead")
    assert without_phone["phone_masked"] is None
    owner = _lead(client, "owner.lead")
    assert owner["phone_masked"] == "+155****0161"


def test_AC_LEAD_005_phone_formatting_does_not_create_a_second_lead(
    client: TestClient,
) -> None:
    """Given the same number written differently, then the second row is a duplicate."""
    _import(client, "format.one,,,,,,+1 555-555-0171,,,\n")
    body = _import(client, "format.two,,,,,,+15555550171,,,\n")
    assert (body["imported"], body["duplicates"]) == (0, 1)
    assert body["errors"][0]["code"] == "DUPLICATE_PHONE"
    assert client.get("/api/v1/leads").json()["total"] == 1
