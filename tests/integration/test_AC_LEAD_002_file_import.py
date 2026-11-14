"""CSV / JSON upload tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient


def _upload(client: TestClient, name: str, content: bytes):
    return client.post(
        "/api/v1/lead-batches/import",
        files={"file": (name, content, "application/octet-stream")},
    )


def test_AC_LEAD_002_csv_with_bom_crlf_and_extra_columns(client: TestClient) -> None:
    """Given a BOM/CRLF CSV with extra columns, when uploaded, then both rows import."""
    content = (
        "﻿username,display_name,region,language,unused\r\n"
        "csv.one,One,US,en,x\r\n"
        "csv.two,Two,GB,en,y\r\n"
    ).encode()
    response = _upload(client, "leads.csv", content)
    assert response.status_code == 201
    body = response.json()
    assert (body["total_rows"], body["imported"], body["source_type"]) == (2, 2, "CSV")
    assert body["source_name"] == "leads.csv"


def test_AC_LEAD_002_json_upload(client: TestClient) -> None:
    """Given a JSON array upload, when parsed, then rows import as JSON source."""
    content = json.dumps(
        [
            {"username": "json.one", "region": "us", "language": "en-US"},
            {"username": "json.two", "bio": "beauty device fan"},
        ]
    ).encode()
    response = _upload(client, "leads.json", content)
    assert response.status_code == 201
    body = response.json()
    assert (body["imported"], body["source_type"]) == (2, "JSON")


def test_AC_LEAD_002_bad_uploads_are_rejected(client: TestClient) -> None:
    """Given an empty, wrong-typed or username-less upload, when sent, then 422 is returned."""
    assert _upload(client, "leads.txt", b"username\nx\n").status_code == 422
    assert _upload(client, "leads.csv", b"").status_code == 422
    assert _upload(client, "leads.csv", b"display_name\nMia\n").status_code == 422
    assert _upload(client, "leads.json", b'{"username": "x"}').status_code == 422
    assert _upload(client, "leads.json", b"not json").status_code == 422
    assert client.get("/api/v1/lead-batches").json()["total"] == 0


def test_AC_LEAD_003_import_normalizes_username_region_language(
    client: TestClient,
) -> None:
    """Given '@Glow.Mia ', 'us' and 'en-US', when imported, then stored normalized."""
    content = b"username,region,language\n@Glow.Mia ,us,en-US\n"
    assert _upload(client, "normalize.csv", content).status_code == 201
    leads = client.get("/api/v1/leads").json()["items"]
    assert len(leads) == 1
    assert leads[0]["username"] == "glow.mia"
    assert leads[0]["region"] == "US"
    assert leads[0]["language"] == "en"
