import pytest


VALID_PAYLOAD = {
    "name": "Иван Петров",
    "email": "ivan@example.com",
    "phone": "+7 999 123-45-67",
    "comment": "Здравствуйте! Ищу backend-разработчика на проект.",
}


def test_valid_contact_returns_200(client):
    r = client.post("/api/contact", json=VALID_PAYLOAD)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["request_id"]
    assert body["insights"]["source"] == "fallback"  # без OPENROUTER_API_KEY
    assert body["insights"]["category"] in (
        "job", "project", "collaboration", "question", "spam", "other",
    )
    assert "X-Request-Id" in {k.title(): v for k, v in r.headers.items()}.keys() \
        or "x-request-id" in r.headers


@pytest.mark.parametrize(
    "field,value,expected_field",
    [
        ("name", "", "name"),
        ("name", "И", "name"),
        ("email", "not-an-email", "email"),
        ("phone", "abc", "phone"),
        ("phone", "12", "phone"),
        ("comment", "x", "comment"),
    ],
)
def test_validation_errors(client, field, value, expected_field):
    payload = {**VALID_PAYLOAD, field: value}
    r = client.post("/api/contact", json=payload)
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    details_fields = {d["field"] for d in body["error"]["details"]}
    assert expected_field in details_fields


def test_client_request_id_is_echoed(client):
    r = client.post(
        "/api/contact",
        json=VALID_PAYLOAD,
        headers={"X-Request-Id": "req-abc-123"},
    )
    assert r.status_code == 200
    assert r.headers.get("x-request-id") == "req-abc-123"
    assert r.json()["request_id"] == "req-abc-123"
