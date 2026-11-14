"""Row validation and warning tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

CSV = (
    "username,display_name,bio,region,language,source_url,phone\n"
    ",NoName,bio,US,en,,+15555550101\n"
    "bad name!,Bad,bio,US,en,,+15555550102\n"
    + "a" * 31
    + ",Long,bio,US,en,,+15555550103\n"
    "ok.region,Region,bio,USA,en,,\n"
    "ok.language,Language,bio,US,e,,\n"
    "ok.phone,Phone,bio,US,en,,12345\n"
    "bad.url,Url,bio,US,en,http://instagram.com/bad,\n"
    "other.url,Url2,bio,US,en,https://example.com/x,\n"
    "ok.nullurl,NullUrl,bio,US,en,,\n"
)


def _import(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/lead-batches/import",
        files={"file": ("rows.csv", CSV.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 201
    return response.json()


def test_AC_LEAD_004_invalid_rows_are_skipped_without_stopping(
    client: TestClient,
) -> None:
    """Given bad usernames, then those rows are invalid and the rest still import."""
    body = _import(client)
    assert (body["total_rows"], body["imported"], body["invalid"]) == (9, 4, 5)
    errors = {(item["row"], item["code"]) for item in body["errors"]}
    assert (1, "MISSING_USERNAME") in errors
    assert (2, "INVALID_USERNAME") in errors
    assert (3, "INVALID_USERNAME") in errors
    assert (7, "INVALID_SOURCE_URL") in errors
    assert (8, "INVALID_SOURCE_URL") in errors
    assert client.get("/api/v1/leads").json()["total"] == 4


def test_AC_LEAD_007_invalid_phone_is_dropped_as_warning(client: TestClient) -> None:
    """Given a non-E.164 phone, when imported, then the lead stays without a phone."""
    body = _import(client)
    assert body["warnings"] == 3
    errors = {(item["row"], item["code"]) for item in body["errors"]}
    assert (4, "INVALID_REGION") in errors
    assert (5, "INVALID_LANGUAGE") in errors
    assert (6, "INVALID_PHONE_DROPPED") in errors
    lead = client.get("/api/v1/leads", params={"q": "ok.phone"}).json()["items"][0]
    assert lead["phone_masked"] is None
    region_lead = client.get("/api/v1/leads", params={"q": "ok.region"}).json()[
        "items"
    ][0]
    assert region_lead["region"] is None


def test_AC_LEAD_010_bad_source_url_rejects_row_but_null_is_allowed(
    client: TestClient,
) -> None:
    """Given http or non-instagram URLs, then rows are invalid; a null URL imports."""
    body = _import(client)
    rejected = {item["row"]: item["code"] for item in body["errors"]}
    assert rejected[7] == "INVALID_SOURCE_URL"
    assert rejected[8] == "INVALID_SOURCE_URL"
    allowed = client.get("/api/v1/leads", params={"q": "ok.nullurl"}).json()
    assert allowed["total"] == 1
    assert allowed["items"][0]["source_url"] is None
