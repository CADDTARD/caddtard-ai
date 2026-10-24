def test_poc_payload_is_explicit_about_evidence_state(client):
    response = client.get("/api/poc")
    assert response.status_code == 200
    body = response.json()
    assert body["counts"]["biology_steps"] == 8
    assert body["counts"]["experimental_groups"] == 7
    assert body["counts"]["development_tiers"] == 4
    assert body["counts"]["go_no_go_gates"] == 7
    assert body["counts"]["validated_gates"] == 0
    assert body["counts"]["copilot_interfaces"] == 8
    assert all(gate["status"] == "planned" for gate in body["go_no_go_gates"])


def test_poc_preserves_variant_and_regulatory_boundaries(client):
    body = client.get("/api/poc").json()
    assert body["program"]["program_variant"] == "c.2267T>G; p.(Leu756Arg)"
    assert "not independently established" in body["evidence_boundary"]["variant_status"]
    assert "not as proof" in body["evidence_boundary"]["model_anchor"]
    fda_source = next(source for source in body["verification_sources"] if source["name"] == "FDA biomarker context of use")
    assert "not a qualified regulatory endpoint" in fda_source["supports"]


def test_poc_copilots_only_report_real_agent_state(client):
    body = client.get("/api/poc").json()
    allowed_states = {"live_evidence", "connected_waiting", "interface_ready"}
    assert {copilot["state"] for copilot in body["execution_copilots"]}.issubset(allowed_states)
    evidence_room = next(copilot for copilot in body["execution_copilots"] if copilot["key"] == "evidence_room_builder")
    assert evidence_room["state"] == "interface_ready"
    assert evidence_room["sources"] == []

