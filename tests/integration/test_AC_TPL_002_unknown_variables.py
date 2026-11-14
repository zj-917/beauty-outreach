"""Template variable whitelist tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.domain.render import extract_variables, unknown_variables


def _create(client: TestClient, *, body: str, name: str = "welcome"):
    return client.post(
        "/api/v1/templates",
        json={"name": name, "body": body, "language": "en"},
    )


def test_AC_TPL_002_extract_variables_in_order() -> None:
    """Given repeated variables, when extracted, then each name appears once in order."""
    assert extract_variables(
        "{{name}} {{ keyword | x }} {{name}}"
    ) == ["name", "keyword"]


def test_AC_TPL_002_unknown_variables_are_unique() -> None:
    """Given repeated unknown variables, when checked, then each unknown name is listed once."""
    assert unknown_variables("{{name}} {{phone}} {{phone}} {{brand}}") == ["phone"]


def test_AC_TPL_002_unknown_variable_is_rejected_on_create(
    client: TestClient,
) -> None:
    """Given an unknown variable, when created, then 422 lists it and nothing is stored."""
    response = _create(client, body="Hi {{name}}, call {{phone}} or {{phone}}")

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "TEMPLATE_UNKNOWN_VARIABLE"
    assert error["details"]["unknown_variables"] == ["phone"]
    assert client.get("/api/v1/templates").json() == []


def test_AC_TPL_002_whitelisted_variables_and_whitespace_are_allowed(
    client: TestClient,
) -> None:
    """Given only whitelisted variables with whitespace, when created, then it succeeds."""
    body = "{{ name }} {{username}} {{ keyword | x }} {{brand}} {{ optout_text }}"

    assert _create(client, body=body).status_code == 201


def test_AC_TPL_002_unknown_variable_is_rejected_on_new_version(
    client: TestClient,
) -> None:
    """Given an unknown variable, when creating a new version, then 422 and no version is added."""
    template_id = _create(client, body="Hi {{name}}").json()["id"]

    response = client.post(
        f"/api/v1/templates/{template_id}/new-version",
        json={"body": "Hi {{phone}}"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TEMPLATE_UNKNOWN_VARIABLE"
    assert len(client.get("/api/v1/templates").json()) == 1


def test_AC_TPL_002_unknown_variable_is_rejected_on_draft_update(
    client: TestClient,
) -> None:
    """Given an unknown variable, when updating a draft, then 422 and the body is unchanged."""
    template_id = _create(client, body="Hi {{name}}").json()["id"]

    response = client.patch(
        f"/api/v1/templates/{template_id}", json={"body": "Hi {{phone}}"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TEMPLATE_UNKNOWN_VARIABLE"
    assert (
        client.get(f"/api/v1/templates/{template_id}").json()["body"] == "Hi {{name}}"
    )
