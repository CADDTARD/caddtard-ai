"""Read-only deployment smoke test for CADDTARD AI."""
import argparse
import json
import time
import urllib.error
import urllib.request
from urllib.parse import quote


# Fields populated from parsed external responses in the current agents.
# Inputs (gene, term, accession, etc.) and summaries are deliberately excluded.
# Unknown/new schemas fail closed until evidence handling is added here.
RETRIEVED_FIELDS = {
    "live_gene_name", "pubmed_hits", "name", "definition", "resolution_angstrom",
    "transcript_count", "constraint", "cid", "hit_count", "monarch_id",
    "model_created", "confidence_version", "pdb_url", "total_count",
    "opentargets_id", "repo_count", "matching_indicators", "total_matching",
    "total_hits", "set_id", "brand_name", "application_number", "total_entries",
}


class VerificationError(RuntimeError):
    pass


def require(condition, message):
    # Unlike assert, deployment gates must still run under python -O.
    if not condition:
        raise VerificationError(message)


def has_response_data(entry):
    for field in RETRIEVED_FIELDS:
        value = entry.get(field)
        # A zero count is evidence; nulls, empty objects and booleans are not.
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            return True
        if isinstance(value, (str, dict, list)) and value:
            return True
    return False


def execution_state(run):
    if not run:
        return "pending"
    status = run.get("status")
    if status == "success":
        return "successful" if run.get("finished_at") else "pending"
    if status in {"running", "queued", "pending"}:
        return "pending"
    # Includes error/partial/cancelled and unknown or missing statuses.
    return "failed"


def retrieval_state(run):
    """Conservative evidence assessment, not an independent live source probe."""
    try:
        detail = json.loads(run.get("detail_json", ""))
    except (TypeError, ValueError):
        return "unavailable", "missing or malformed run detail"
    if not isinstance(detail, dict):
        return "unavailable", "run detail is not an object"
    if detail.get("configured") is False:
        return "unconfigured", detail.get("note", "integration is not configured")
    if "error" in detail:
        return "unavailable", str(detail["error"])
    entries = []
    for key in ("findings", "counts", "terms", "structures", "genes", "searches"):
        value = detail.get(key, [])
        if not isinstance(value, list):
            return "unavailable", f"invalid evidence collection: {key}"
        entries.extend(value)
    if not entries:
        return "unavailable", "no external response evidence recorded"
    failures = []
    verified = 0
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            failures.append(f"entry {index}: invalid evidence")
        elif "error" in entry or "http_status" in entry:
            failures.append(f"entry {index}: {entry.get('error', 'HTTP ' + str(entry.get('http_status')))}")
        elif has_response_data(entry):
            verified += 1
        else:
            failures.append(f"entry {index}: no recognized response data")
    if verified == len(entries):
        return "verified", f"{verified}/{len(entries)} entries contain parsed response data"
    return "unavailable", f"{verified}/{len(entries)} entries verified; " + "; ".join(failures)


def validate_roster(agents, expected_keys=None):
    keys = [agent["key"] for agent in agents]
    require(len(keys) == len(set(keys)) == 20, "expected 20 distinct implemented agents")
    if expected_keys is not None:
        require(set(keys) == expected_keys, "implemented agent roster changed during verification")
    return set(keys)


def report_agents(base_url, agents):
    retrieval = {}
    for agent in agents:
        key = agent["key"]
        run = agent.get("last_run")
        state = execution_state(run)
        external, reason = "unavailable", "execution has not succeeded"
        if state == "successful":
            try:
                latest = get_json(base_url, f"/api/agents/{quote(key, safe='')}/latest")
                if latest.get("id") != run.get("id") or execution_state(latest) != "successful":
                    reason = "latest run changed during verification; rerun the check"
                    # Do not hide a newer failed/running run behind the earlier
                    # successful list snapshot.
                    agent["last_run"] = run = latest
                    state = execution_state(latest)
                else:
                    external, reason = retrieval_state(latest)
            except (urllib.error.URLError, ValueError) as exc:
                reason = f"run detail unavailable: {exc}"
        retrieval[key] = external
        print(f"Agent {key}: execution={state}; status={(run or {}).get('status', 'not run')}; "
              f"finished_at={(run or {}).get('finished_at')}; "
              f"external_data={external}; {reason}; summary={(run or {}).get('summary', '')}")
    return retrieval


def verify_agents(base_url, agents, wait=False, require_external=False):
    expected_keys = validate_roster(agents)
    deadline = time.monotonic() + 300
    while wait:
        states = [execution_state(agent.get("last_run")) for agent in agents]
        if "failed" in states or "pending" not in states or time.monotonic() >= deadline:
            break
        time.sleep(min(10, max(0, deadline - time.monotonic())))
        agents = get_json(base_url, "/api/agents?status=implemented")
        validate_roster(agents, expected_keys)
    retrieval = report_agents(base_url, agents)
    failed = [agent["key"] for agent in agents if execution_state(agent.get("last_run")) == "failed"]
    require(not failed, "agent execution failed: " + ", ".join(failed))
    if wait:
        pending = [agent["key"] for agent in agents if execution_state(agent.get("last_run")) != "successful"]
        require(not pending, "agent successful-run proof timed out: " + ", ".join(pending))
        print("Function execution: all 20 latest runs succeeded and have completion timestamps")
    else:
        print("Function execution: not required (use --wait-for-agents)")
    if require_external:
        unverified = [key for key, state in retrieval.items() if state != "verified"]
        require(not unverified, "external data retrieval not verified: " + ", ".join(unverified))
        print("External data retrieval: verified from recorded latest-run evidence for all 20 agents")
    else:
        print("External data retrieval: diagnostic only (use --require-external-data to enforce)")


def get_json(base_url: str, path: str):
    with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=20) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", help="Deployed origin, e.g. https://caddtard-ai.example")
    parser.add_argument("--wait-for-agents", action="store_true", help="Wait up to five minutes for all latest runs to succeed")
    parser.add_argument("--require-external-data", action="store_true",
                        help="Require parsed external response evidence for every agent; implies --wait-for-agents")
    args = parser.parse_args()

    health = get_json(args.base_url, "/health")
    ready = get_json(args.base_url, "/health/ready")
    agents = get_json(args.base_url, "/api/agents?status=implemented")
    portfolio = get_json(args.base_url, "/api/dashboard/health")
    operations = get_json(args.base_url, "/api/ops/summary")

    require(health["status"] == "ok", "liveness failed")
    require(ready["status"] == "ready", "readiness failed")
    require(ready["database"] is True, "database is not ready")
    require(ready["scheduler_running"] is True, "scheduler is not running")
    require(ready["registered_jobs"] == ready["expected_jobs"] == 20, "expected 20 registered scheduler jobs")
    validate_roster(agents)
    require(len(portfolio) == 3, "expected 3 portfolio entries")
    require(operations["study_count"] >= 1, "expected at least one study")

    print("Scheduler readiness: passed (20 registered jobs); this does not prove execution or retrieval")
    verify_agents(args.base_url, agents, args.wait_for_agents or args.require_external_data,
                  args.require_external_data)

    print("CADDTARD AI smoke test passed for the requested checks; no independent live source probe performed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (VerificationError, urllib.error.URLError, ValueError, KeyError, TypeError) as exc:
        print(f"CADDTARD AI smoke test failed: {exc}")
        raise SystemExit(1)
