from tests.test_contact_validation import VALID_PAYLOAD


def test_rate_limit_kicks_in(client, monkeypatch):
    # Понижаем лимит для скорости.
    from app.core import config
    monkeypatch.setattr(config.settings, "rate_limit_max", 2)
    monkeypatch.setattr(config.settings, "rate_limit_window_seconds", 60)

    for _ in range(2):
        r = client.post("/api/contact", json=VALID_PAYLOAD)
        assert r.status_code == 200, r.text

    r = client.post("/api/contact", json=VALID_PAYLOAD)
    assert r.status_code == 429
    body = r.json()
    assert body["error"]["code"] == "rate_limited"
    assert "Повторите через" in body["error"]["message"]
