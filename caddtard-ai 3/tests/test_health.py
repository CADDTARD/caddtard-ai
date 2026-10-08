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
    assert body["registered_jobs"] == 0
    assert body["expected_jobs"] == 0


def test_dashboard_uses_real_health_route(client):
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    javascript = client.get("/app.js")
    assert javascript.status_code == 200
    assert "api('/health')" in javascript.text
    assert "api('/api/health')" not in javascript.text


def test_public_read_only_blocks_mutations_but_allows_reads(client, monkeypatch):
    from app.main import settings

    monkeypatch.setattr(settings, "public_read_only", True)

    blocked = client.post("/api/agents/genomics/run")
    assert blocked.status_code == 403
    assert blocked.json() == {"detail": "This public deployment is read-only."}

    assert client.get("/health").status_code == 200
