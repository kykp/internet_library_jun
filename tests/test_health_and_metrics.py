from tests.test_contact_validation import VALID_PAYLOAD


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert "smtp" in body["checks"]
    assert "ai" in body["checks"]


def test_metrics_empty(client):
    r = client.get("/api/metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["total_requests"] == 0
    assert body["successful"] == 0
    assert body["failed"] == 0


def test_metrics_increment_on_contact(client):
    client.post("/api/contact", json=VALID_PAYLOAD)
    r = client.get("/api/metrics")
    body = r.json()
    assert body["total_requests"] == 1
    assert body["successful"] == 1
    assert body["last_request_at"] is not None
