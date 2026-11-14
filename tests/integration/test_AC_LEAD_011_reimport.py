"""Repeated mock import tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_AC_LEAD_011_second_import_only_counts_duplicates(client: TestClient) -> None:
    """Given the same dataset twice, then the second run imports nothing and keeps totals."""
    first = client.post(
        "/api/v1/lead-batches/import", json={"source": "mock"}
    ).json()
    assert (first["imported"], first["duplicates"]) == (44, 4)
    second = client.post(
        "/api/v1/lead-batches/import", json={"source": "mock"}
    ).json()
    assert (
        second["total_rows"],
        second["imported"],
        second["duplicates"],
        second["invalid"],
        second["warnings"],
    ) == (52, 0, 48, 4, 1)
    assert client.get("/api/v1/leads").json()["total"] == 44
