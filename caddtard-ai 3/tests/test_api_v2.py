"""Tests for the v2.0 layers: data fabric, knowledge graph, agent taxonomy
filters, reasoning engine, laboratory OS, and executive dashboard."""


def test_sources_list_and_counts(client):
    resp = client.get("/api/sources")
    assert resp.status_code == 200
    sources = resp.json()
    assert len(sources) == 39
    connected = [s for s in sources if s["status"] == "connected"]
    assert len(connected) == 19
    keys = {s["key"] for s in connected}
    assert {"uniprot", "pubmed", "pdb", "quickgo"}.issubset(keys)


def test_sources_filter_by_status(client):
    resp = client.get("/api/sources", params={"status": "planned"})
    assert resp.status_code == 200
    assert all(s["status"] == "planned" for s in resp.json())
    assert len(resp.json()) == 19


def test_agents_division_filter(client):
    resp = client.get("/api/agents", params={"division": "Genomics"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 8
    assert all(a["division"] == "Genomics" for a in body)


def test_agents_status_filter(client):
    resp = client.get("/api/agents", params={"status": "implemented"})
    assert resp.status_code == 200
    assert len(resp.json()) == 20


def test_agents_divisions_endpoint(client):
    resp = client.get("/api/agents/divisions")
    assert resp.status_code == 200
    divisions = resp.json()
    assert "Genomics" in divisions
    assert "Development" in divisions


def test_trigger_planned_agent_returns_409(client):
    planned = client.get("/api/agents", params={"status": "planned"}).json()
    assert len(planned) > 0
    key = planned[0]["key"]
    resp = client.post(f"/api/agents/{key}/run")
    assert resp.status_code == 409


def test_graph_nodes_and_gene_subgraph(client):
    resp = client.get("/api/graph/nodes", params={"node_type": "gene"})
    assert resp.status_code == 200
    genes = resp.json()
    assert len(genes) == 13
    labels = {n["label"] for n in genes}
    assert "ATP6V0C" in labels

    resp2 = client.get("/api/graph/genes/ATP6V0C/subgraph", params={"depth": 2})
    assert resp2.status_code == 200
    sub = resp2.json()
    assert len(sub["nodes"]) >= 1
    assert any(n["label"] == "ATP6V0C" for n in sub["nodes"])


def test_graph_gene_subgraph_404(client):
    resp = client.get("/api/graph/genes/NOTAGENE/subgraph")
    assert resp.status_code == 404


def test_hypotheses_list_and_filter(client):
    resp = client.get("/api/hypotheses")
    assert resp.status_code == 200
    hyps = resp.json()
    assert len(hyps) == 3
    numbers = {h["number"] for h in hyps}
    assert {17, 18, 19}.issubset(numbers)
    for h in hyps:
        assert 0.0 <= h["overall_confidence"] <= 1.0
        assert len(h["steps"]) > 0

    resp2 = client.get("/api/hypotheses", params={"gene": "ATP6V0C"})
    assert resp2.status_code == 200
    assert all(h["gene_symbol"] == "ATP6V0C" for h in resp2.json())


def test_hypothesis_by_number(client):
    resp = client.get("/api/hypotheses/17")
    assert resp.status_code == 200
    assert resp.json()["number"] == 17


def test_hypothesis_404(client):
    resp = client.get("/api/hypotheses/9999")
    assert resp.status_code == 404


def test_lab_experiment_crud_flow(client):
    create = client.post("/api/lab/experiments", json={
        "title": "Lysosomal pH assay, ATP6V0C patient fibroblasts",
        "candidate_slug": "atp6v0c",
        "objective": "Confirm decreased lysosomal acidification",
        "assay_type": "microscopy",
        "status": "planned",
        "owner": "test-suite",
    })
    assert create.status_code == 201
    exp = create.json()
    exp_id = exp["id"]

    listed = client.get("/api/lab/experiments", params={"candidate": "atp6v0c"})
    assert listed.status_code == 200
    assert any(e["id"] == exp_id for e in listed.json())

    updated = client.patch(f"/api/lab/experiments/{exp_id}", json={"status": "in_progress"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"

    note = client.post(f"/api/lab/experiments/{exp_id}/notebook", json={
        "author": "test-suite", "content_markdown": "Set up assay plate.",
    })
    assert note.status_code == 201

    result = client.post(f"/api/lab/experiments/{exp_id}/results", json={
        "assay_type": "microscopy", "summary": "Reduced LysoTracker signal vs control",
        "data": {"n": 3}, "file_ref": "",
    })
    assert result.status_code == 201
    assert result.json()["data"] == {"n": 3}


def test_lab_experiment_404(client):
    resp = client.get("/api/lab/experiments/999999")
    assert resp.status_code == 404


def test_lab_reagents(client):
    resp = client.get("/api/lab/reagents")
    assert resp.status_code == 200

    created = client.post("/api/lab/reagents", json={
        "name": "LysoTracker Red DND-99", "vendor": "Thermo", "quantity": 1, "reorder_threshold": 2,
    })
    assert created.status_code == 201

    low_stock = client.get("/api/lab/reagents", params={"low_stock_only": True})
    assert low_stock.status_code == 200
    assert any(r["name"] == "LysoTracker Red DND-99" for r in low_stock.json())


def test_lab_recommendations_are_sorted_ascending_by_confidence(client):
    resp = client.get("/api/lab/recommendations")
    assert resp.status_code == 200
    recs = resp.json()
    assert len(recs) > 0
    confidences = [r["step"]["confidence"] for r in recs]
    assert confidences == sorted(confidences)
    for r in recs:
        assert r["step"]["recommended_next_experiment"] != ""
        assert r["step"]["experimental_status"] != "validated"


def test_dashboard_health_single_candidate(client):
    resp = client.get("/api/dashboard/health/drta")
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidate_slug"] == "drta"
    assert 0.0 <= body["checklist_completion_pct"] <= 100.0
    assert body["scoring_composite"] > 0


def test_dashboard_health_404(client):
    resp = client.get("/api/dashboard/health/not-a-real-slug")
    assert resp.status_code == 404


def test_dashboard_health_portfolio(client):
    resp = client.get("/api/dashboard/health")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    assert {h["candidate_slug"] for h in body} == {"drta", "atp6v0c", "tcirg1"}


def test_operations_summary(client):
    resp = client.get("/api/ops/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["vendor_count"] >= 1
    assert body["study_count"] >= 1
    assert body["demo_study_count"] == 1
    assert body["studies"][0]["is_demo"] is True
    assert body["readiness"]
