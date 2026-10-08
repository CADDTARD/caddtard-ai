"""Read-only deployment smoke test for CADDTARD AI."""
import argparse
import json
import time
import urllib.error
import urllib.request


def get_json(base_url: str, path: str):
    with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=20) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", help="Deployed origin, e.g. https://caddtard-ai.example")
    parser.add_argument("--wait-for-agents", action="store_true", help="Wait up to five minutes for every first run")
    args = parser.parse_args()

    health = get_json(args.base_url, "/health")
    ready = get_json(args.base_url, "/health/ready")
    agents = get_json(args.base_url, "/api/agents?status=implemented")
    portfolio = get_json(args.base_url, "/api/dashboard/health")
    operations = get_json(args.base_url, "/api/ops/summary")

    assert health["status"] == "ok"
    assert ready["status"] == "ready"
    assert ready["database"] is True
    assert ready["scheduler_running"] is True
    assert ready["registered_jobs"] == ready["expected_jobs"] == 20
    assert len(agents) == 20
    assert len(portfolio) == 3
    assert operations["study_count"] >= 1

    if args.wait_for_agents:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            agents = get_json(args.base_url, "/api/agents?status=implemented")
            if all(agent["last_run"] and agent["last_run"]["finished_at"] for agent in agents):
                break
            time.sleep(10)
        assert all(agent["last_run"] and agent["last_run"]["finished_at"] for agent in agents), "agent first-run proof timed out"

    print("CADDTARD AI smoke test passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, urllib.error.URLError) as exc:
        print(f"CADDTARD AI smoke test failed: {exc}")
        raise SystemExit(1)
