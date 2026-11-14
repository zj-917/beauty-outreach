"""Phone encryption and leak-scan tests."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Lead

PHONE = "+15555550151"


def test_AC_LEAD_008_phone_is_encrypted_hashed_and_masked(
    client: TestClient, tmp_path: Path
) -> None:
    """Given a lead with a phone, when imported, then storage and responses contain no plaintext."""
    content = f"username,phone\nsecure.lead,{PHONE}\n".encode()
    response = client.post(
        "/api/v1/lead-batches/import",
        files={"file": ("secure.csv", content, "text/csv")},
    )
    assert response.status_code == 201

    cipher = client.app.state.phone_cipher
    with Session(client.app.state.engine) as session:
        lead = session.scalar(select(Lead).where(Lead.username == "secure.lead"))
        assert lead is not None
        assert cipher.decrypt(lead.phone_enc or "") == PHONE
        assert lead.phone_hash == cipher.hash_phone(PHONE)
        assert lead.phone_masked == "+155****0151"

    detail = client.get("/api/v1/leads/1").json()
    assert detail["phone_masked"] == "+155****0151"
    assert "phone_enc" not in detail
    assert "phone_hash" not in detail
    assert PHONE not in json.dumps(detail)
    assert PHONE not in json.dumps(client.get("/api/v1/leads").json())

    digits = PHONE.removeprefix("+").encode()
    for path in tmp_path.glob("test.db*"):
        data = path.read_bytes()
        assert digits not in data, f"plaintext phone found in {path.name}"
