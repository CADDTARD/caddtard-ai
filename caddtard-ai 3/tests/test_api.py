def test_list_genes(client):
    resp = client.get("/api/genes")
    assert resp.status_code == 200
    genes = resp.json()
    assert len(genes) == 13
    symbols = {g["symbol"] for g in genes}
    assert {"ATP6V0A4", "ATP6V1B1", "ATP6V0C", "TCIRG1", "VMA21"}.issubset(symbols)


def test_top3_only_filter(client):
    resp = client.get("/api/genes", params={"top3_only": True})
    assert resp.status_code == 200
    genes = resp.json()
    assert {g["symbol"] for g in genes} == {"ATP6V0A4", "ATP6V1B1", "ATP6V0C", "TCIRG1"}


def test_get_gene_with_variants(client):
    resp = client.get("/api/genes/ATP6V0A4")
    assert resp.status_code == 200
    gene = resp.json()
    assert gene["uniprot_accession"] == "Q9HBG4"
    assert gene["xlsx_uniprot_claim"] == "Q9H1X4"  # the accession error caught during research
    assert len(gene["variants"]) > 0


def test_get_gene_404(client):
    resp = client.get("/api/genes/NOTAGENE")
    assert resp.status_code == 404


def test_variants_filter_by_gene(client):
    resp = client.get("/api/variants", params={"gene": "TCIRG1"})
    assert resp.status_code == 200
    # TCIRG1 was added from literature, not present in the originally uploaded xlsx
    assert resp.json() == []


def test_scoring_sorted_desc(client):
    resp = client.get("/api/scoring")
    assert resp.status_code == 200
    scores = [row["composite"] for row in resp.json()]
    assert scores == sorted(scores, reverse=True)
    assert len(resp.json()) == 10


def test_candidates_top3(client):
    resp = client.get("/api/candidates")
    assert resp.status_code == 200
    slugs = {c["slug"] for c in resp.json()}
    assert slugs == {"drta", "atp6v0c", "tcirg1"}


def test_candidate_detail_has_timeline_and_cost(client):
    resp = client.get("/api/candidates/tcirg1")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["timeline"]) > 0
    assert body["cost_summary"]["allin_low_usd_k"] == 4000


def test_candidate_404(client):
    resp = client.get("/api/candidates/not-a-real-slug")
    assert resp.status_code == 404


def test_checklist_default_state_and_toggle(client):
    resp = client.get("/api/checklist", params={"candidate": "drta"})
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 12
    assert all(item["checked"] is False for item in items)

    item_id = items[0]["id"]
    toggled = client.patch(f"/api/checklist/{item_id}", json={"checked": True})
    assert toggled.status_code == 200
    assert toggled.json()["checked"] is True

    resp2 = client.get("/api/checklist", params={"candidate": "drta"})
    assert any(item["checked"] for item in resp2.json())


def test_checklist_toggle_404(client):
    resp = client.patch("/api/checklist/999999", json={"checked": True})
    assert resp.status_code == 404


def test_agents_list(client):
    """As of v2.0 this returns the full ~52-agent taxonomy (see
    tests/test_api_v2.py for division/status filtering); the 4 original v1
    agents must still be present and implemented."""
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    body = resp.json()
    keys = {a["key"] for a in body}
    assert {"genomics", "literature", "structural", "ontology"}.issubset(keys)
    v1_agents = [a for a in body if a["key"] in {"genomics", "literature", "structural", "ontology"}]
    assert all(a["status"] == "implemented" for a in v1_agents)


def test_agent_manual_trigger_records_a_run(client):
    """Runs end-to-end against real external APIs when network is available;
    when it is not (e.g. an offline CI runner) the agent still completes and
    is recorded with status='error' rather than crashing - this asserts the
    audit trail exists either way, not that the network call succeeded."""
    resp = client.post("/api/agents/genomics/run")
    assert resp.status_code == 202

    history = client.get("/api/agents/genomics/runs")
    assert history.status_code == 200
    assert len(history.json()) >= 1
    assert history.json()[0]["status"] in ("success", "error", "running")


def test_agent_unknown_name_404(client):
    resp = client.post("/api/agents/not-a-real-agent/run")
    assert resp.status_code == 404
