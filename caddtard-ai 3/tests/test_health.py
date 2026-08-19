def test_liveness(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "CADDTARD AI"


def test_readiness(client):
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] is True
    # scheduler is intentionally disabled in the test environment (AGENTS_ENABLED=false)
    assert body["scheduler_running"] is True  # readiness treats "disabled" as trivially ready
