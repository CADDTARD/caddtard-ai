"""Deployment verification regressions; no external network or scheduler needed."""
import copy
import json
import subprocess
import sys
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.agents.base import agent_run
from app.models import AgentRun
from app.schemas import AgentRunOut
from scripts import smoke_test as smoke


@pytest.fixture
def agents(monkeypatch):
    rows = [{"key": f"agent_{i}", "last_run": {
        "id": i, "status": "success", "finished_at": "2026-10-09T12:00:00",
        "summary": "Completed",
    }} for i in range(20)]

    def get_json(base, path):
        key = path.split("/")[-2]
        run = next(row["last_run"] for row in rows if row["key"] == key)
        return {**run, "detail_json": json.dumps({"counts": [{"pubmed_hits": 0}]})}

    monkeypatch.setattr(smoke, "get_json", get_json)
    return rows


def test_real_framework_error_with_finished_at_fails_verification(agents):
    engine = create_engine("sqlite://")
    AgentRun.__table__.create(engine)
    try:
        with Session(engine) as db:
            with agent_run(db, "agent_0", None, "scheduled"):
                raise RuntimeError("source request failed")
            run = db.scalar(select(AgentRun))
            assert run.status == "error" and run.finished_at is not None
            agents[0]["last_run"] = AgentRunOut.model_validate(run).model_dump(mode="json")
            with pytest.raises(smoke.VerificationError, match="agent execution failed: agent_0"):
                smoke.verify_agents("https://unused", agents, wait=True)
    finally:
        engine.dispose()


@pytest.mark.parametrize("run", [None, {"status": "running", "finished_at": None},
                                  {"status": "success", "finished_at": None}])
def test_pending_runs_timeout_with_diagnostics(agents, monkeypatch, capsys, run):
    agents[0]["last_run"] = run
    clock = iter([0, 301])
    monkeypatch.setattr(smoke.time, "monotonic", lambda: next(clock))
    with pytest.raises(smoke.VerificationError, match="timed out: agent_0"):
        smoke.verify_agents("https://unused", agents, wait=True)
    assert "Agent agent_0: execution=pending" in capsys.readouterr().out


def test_pending_poll_transitions_to_success(agents, monkeypatch):
    ready = copy.deepcopy(agents)
    agents[0]["last_run"] = None
    original_get = smoke.get_json
    monkeypatch.setattr(smoke.time, "sleep", lambda _: None)
    def get_json(base, path):
        if "?status=" in path:
            agents[:] = copy.deepcopy(ready)
            return agents
        return original_get(base, path)
    monkeypatch.setattr(smoke, "get_json", get_json)
    smoke.verify_agents("https://unused", agents, wait=True, require_external=True)


@pytest.mark.parametrize("rows", [[], [{"key": "duplicate"}] * 20])
def test_missing_or_duplicate_roster_cannot_pass(rows):
    with pytest.raises(smoke.VerificationError, match="20 distinct"):
        smoke.verify_agents("https://unused", rows, wait=True)


def test_roster_changed_during_poll_fails(agents, monkeypatch):
    agents[0]["last_run"] = None
    updated = copy.deepcopy(agents)
    updated[0]["key"] = "replacement"
    monkeypatch.setattr(smoke.time, "sleep", lambda _: None)
    monkeypatch.setattr(smoke, "get_json", lambda *_: updated)
    with pytest.raises(smoke.VerificationError, match="roster changed"):
        smoke.verify_agents("https://unused", agents, wait=True)


@pytest.mark.parametrize("status", ["error", "partial", "cancelled", "unexpected", None])
def test_non_success_terminal_status_fails(agents, status):
    agents[0]["last_run"]["status"] = status
    with pytest.raises(smoke.VerificationError, match="agent execution failed"):
        smoke.verify_agents("https://unused", agents, wait=True)


@pytest.mark.parametrize("detail,state", [
    ({"configured": False, "note": "missing API key"}, "unconfigured"),
    ({"searches": [{"error": "timeout"}]}, "unavailable"),
    ({"searches": [{"http_status": 503}]}, "unavailable"),
    ({"counts": [{"pubmed_hits": 2}, {"error": "timeout"}]}, "unavailable"),
    ({"genes": [{"gene": "ATP6V0A1"}]}, "unavailable"),
    ({"genes": [{"constraint": None}]}, "unavailable"),
    ({"genes": [{"constraint": {}}]}, "unavailable"),
    ({"searches": []}, "unavailable"),
    ({"searches": None}, "unavailable"),
    ([], "unavailable"),
    ({"counts": [{"pubmed_hits": 0}]}, "verified"),
])
def test_external_evidence_assessment(detail, state):
    assert smoke.retrieval_state({"detail_json": json.dumps(detail)})[0] == state


@pytest.mark.parametrize("detail", ["", "{truncated", None])
def test_invalid_details_are_unavailable(detail):
    assert smoke.retrieval_state({"detail_json": detail})[0] == "unavailable"


def test_execution_success_does_not_imply_retrieval(agents, monkeypatch, capsys):
    monkeypatch.setattr(smoke, "get_json", lambda *_: {
        **agents[0]["last_run"], "detail_json": '{"configured": false}'})
    smoke.verify_agents("https://unused", agents, wait=True)
    assert "execution=successful" in capsys.readouterr().out
    with pytest.raises(smoke.VerificationError, match="external data retrieval not verified"):
        smoke.verify_agents("https://unused", agents, wait=True, require_external=True)


@pytest.mark.parametrize("changed", [True, False])
def test_detail_endpoint_unavailable_or_run_changed(agents, monkeypatch, changed):
    def get_json(*_):
        if changed:
            return {"id": 999, "status": "success", "finished_at": "today"}
        raise urllib.error.HTTPError("https://unused", 404, "Not Found", None, None)
    monkeypatch.setattr(smoke, "get_json", get_json)
    with pytest.raises(smoke.VerificationError, match="external data retrieval not verified"):
        smoke.verify_agents("https://unused", agents, wait=True, require_external=True)


def test_all_successful_runs_and_zero_hit_responses_pass(agents):
    smoke.verify_agents("https://unused", agents, wait=True, require_external=True)


def test_new_failed_run_cannot_hide_behind_successful_list_snapshot(agents, monkeypatch):
    monkeypatch.setattr(smoke, "get_json", lambda *_: {
        "id": 999, "status": "error", "finished_at": "2026-10-09T12:01:00"})
    with pytest.raises(smoke.VerificationError, match="agent execution failed"):
        smoke.verify_agents("https://unused", agents, wait=True)


@pytest.mark.parametrize("strict", [False, True])
def test_cli_main_failure_and_strict_mode(agents, monkeypatch, strict):
    endpoints = {
        "/health": {"status": "ok"},
        "/health/ready": {"status": "ready", "database": True, "scheduler_running": True,
                          "registered_jobs": 20, "expected_jobs": 20},
        "/api/agents?status=implemented": agents,
        "/api/dashboard/health": [1, 2, 3],
        "/api/ops/summary": {"study_count": 1},
    }
    original_get = smoke.get_json
    monkeypatch.setattr(smoke, "get_json", lambda base, path:
                        endpoints[path] if path in endpoints else original_get(base, path))
    monkeypatch.setattr(sys, "argv", ["smoke_test.py", "https://unused",
                                    "--require-external-data" if strict else "--wait-for-agents"])
    assert smoke.main() == 0
    agents[0]["last_run"]["status"] = "error"
    with pytest.raises(smoke.VerificationError, match="agent execution failed"):
        smoke.main()


def test_optimized_python_keeps_failure_gate():
    result = subprocess.run([sys.executable, "-O", "-c",
                             "from scripts.smoke_test import require; require(False, 'failed')"],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert result.returncode != 0
    assert "VerificationError: failed" in result.stderr


@pytest.mark.parametrize("status,exit_code", [("error", 1), ("success", 0)])
def test_real_cli_exit_against_local_http_fixture(agents, status, exit_code):
    agents[0]["last_run"]["status"] = status
    endpoints = {
        "/health": {"status": "ok"},
        "/health/ready": {"status": "ready", "database": True, "scheduler_running": True,
                          "registered_jobs": 20, "expected_jobs": 20},
        "/api/agents?status=implemented": agents,
        "/api/dashboard/health": [1, 2, 3],
        "/api/ops/summary": {"study_count": 1},
    }
    for row in agents:
        endpoints[f"/api/agents/{row['key']}/latest"] = {
            **row["last_run"], "detail_json": '{"counts": [{"pubmed_hits": 0}]}'}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(endpoints[self.path]).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        result = subprocess.run([
            sys.executable, "scripts/smoke_test.py", f"http://127.0.0.1:{server.server_port}",
            "--require-external-data"], cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=10)
        assert result.returncode == exit_code
        if exit_code:
            assert "agent execution failed: agent_0" in result.stdout
            assert "smoke test passed" not in result.stdout
        else:
            assert "smoke test passed for the requested checks" in result.stdout
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
