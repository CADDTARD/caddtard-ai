def test_compound_summary_is_explicit_about_verification_and_fto(client):
    response = client.get("/api/compounds/summary")
    assert response.status_code == 200
    summary = response.json()
    assert summary["total"] == 18
    assert summary["verified"] > 0
    assert summary["unverified"] > 0
    assert summary["identity_verified"] >= summary["verified"]
    assert summary["fto_cleared"] == 0


def test_compound_filters_and_evidence_ledger(client):
    response = client.get("/api/compounds", params={"verification": "verified"})
    assert response.status_code == 200
    compounds = response.json()
    assert compounds
    assert all(c["verification_status"] == "verified" for c in compounds)
    assert all(c["evidence"] for c in compounds)
    assert any(c["slug"] == "bafilomycin-a1" for c in compounds)
    assert all(c["identity_verified"] and c["mechanism_verified"] for c in compounds)
    assert all(any(e["evidence_type"] == "primary_research" for e in c["evidence"]) for c in compounds)


def test_niclosamide_is_not_misrepresented_as_direct_inhibitor(client):
    response = client.get("/api/compounds/niclosamide")
    assert response.status_code == 200
    compound = response.json()
    assert compound["role"] == "pathway_adjacent"
    assert "V-ATPase-independent" in compound["caveat"]


def test_thin_data_entries_are_quarantined(client):
    response = client.get("/api/compounds", params={"role": "thin_data"})
    assert response.status_code == 200
    compounds = response.json()
    assert [c["slug"] for c in compounds] == ["ipi"]
    assert compounds[0]["verification_status"] == "unverified"
    assert compounds[0]["identity_verified"] is False


def test_compound_404(client):
    response = client.get("/api/compounds/not-a-real-compound")
    assert response.status_code == 404

