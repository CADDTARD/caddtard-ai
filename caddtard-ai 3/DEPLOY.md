# Deploying CADDTARD AI v3.1 MVP continuously

Everything in this repo was written and verified inside a sandbox with no
outbound access to PyPI and no persistent public hostname (see
`ARCHITECTURE.md`'s "Continuous operation" section) - so "runs continuously"
could only be proven as code + logic in that environment, not as a live
deployment. This file is the concrete, real path to making it one.

The app is a standard Docker Compose stack (`api` + `db`), so it deploys to
any container host. Two free-tier-friendly options below.

## Pre-deployment gate

From `caddtard-ai 3/`, run:

```bash
pip install -r requirements-dev.txt
pytest -q
python scripts/migrate.py
alembic check
docker compose up --build
```

Confirm `/health/ready` reports matching `registered_jobs` and `expected_jobs`.
Keep the API at one process and one replica while APScheduler is embedded in
the web process; scaling horizontally requires moving the scheduler to a
dedicated worker first.

## Option A — Render

Render's MCP connector (`mcp.render.com`) can drive this whole flow from
inside a chat session once connected - `create_postgres`, `create_web_service`,
and `get_deploy`/`get_metrics` cover the steps below without leaving the chat.

Manual steps (same result):

1. Use the repository-root `render.yaml` Blueprint.
2. Select an always-on web plan; sleeping instances cannot prove continuous scheduling.
3. Confirm the service root is `caddtard-ai 3` and health path is `/health/ready`.
4. Environment variables:
   - `DATABASE_URL` = the Postgres internal connection string from step 2
     (Render's string is `postgresql://...`; SQLAlchemy needs the
     `postgresql+psycopg2://` prefix - swap it)
   - `CORS_ORIGINS` = your Render service's `*.onrender.com` URL
   - `AGENTS_ENABLED` = `true`
   - `PATENTSVIEW_API_KEY` = optional, see `.env.example`
5. Health check path: `/health/ready`
6. Deploy. The scheduler starts in `main.py`'s FastAPI lifespan handler on
   boot and keeps running for as long as the Render service is up. Use an
   always-on instance; a sleeping service is not continuous operation.

## Option B — Railway

Railway's MCP connector (`mcp.railway.com`) exposes `create-project`,
`deploy-artifact`, `get-logs`, `get-status` directly.

Manual steps:

1. **New Project > Deploy from GitHub repo** and set the service root directory to `caddtard-ai 3`.
2. **New > Database > PostgreSQL** in the same project (Railway wires
   `DATABASE_URL` into other services automatically if you reference it as
   `${{Postgres.DATABASE_URL}}`; adjust the scheme prefix to
   `postgresql+psycopg2://` as above).
3. Railway reads `railway.json` from that service root. Set the same environment variables as the Render list above.
4. Railway services don't sleep on the Hobby plan the way Render's free tier
   does, which matters for a scheduler-driven app like this one.

## After either deploy

Run the read-only deployment checks. The optional flag waits up to five
minutes for all 20 agents' latest runs to have both `status="success"` and
`finished_at`. An `error` run fails immediately even if it has a completion
timestamp. Pending runs fail on timeout; missing, duplicate, or changing
agent rosters also fail.

```bash
python scripts/smoke_test.py https://YOUR_DEPLOYED_HOST --wait-for-agents
```

Verification has three separate levels:

- **Scheduler readiness:** `/health/ready` reports 20 expected and registered
  jobs. Registration alone does not prove that any job executed.
- **Function execution:** `--wait-for-agents` requires successful completed
  latest runs. It rejects errors and unknown terminal statuses. It does not
  guarantee retrieval: agents can catch source errors internally or return
  successfully when credentials are absent.
- **External retrieval evidence:** each successful run is inspected using the
  existing `GET /api/agents/{key}/latest` endpoint. Diagnostics distinguish
  verified parsed response data, unavailable evidence (including partial
  results, HTTP errors, malformed/truncated details and unknown schemas),
  and unconfigured integrations such as missing `PATENTSVIEW_API_KEY`.
  Counts of zero are valid parsed responses, not proof of matching records.

For a strict retrieval gate, use:

```bash
python scripts/smoke_test.py https://YOUR_DEPLOYED_HOST --require-external-data
```

This implies `--wait-for-agents` and fails unless every agent's latest run
contains recognized response data for every recorded query. No integration
is silently exempted; configure the patent API key before expecting this
strict check to pass. Existing `--wait-for-agents` callers retain an execution
gate with retrieval diagnostics, without requiring optional credentials.

Evidence is based on the application's recorded run details, not an
independent source probe. Unknown/new detail schemas remain unverified until
the smoke test's evidence handling is extended. A run changing between list
and detail reads is reported as unverified. These checks do not trigger jobs,
require an admin token, impose freshness limits, or prove repeated scheduled
operation: latest runs may be old or manually triggered. Review timestamps,
triggers and run history for those claims. Without either option, the check
reports pending execution without waiting, but still rejects observed failed
runs. Its pass message applies only to the requested verification level.

The existing GitHub Actions pytest jobs discover the smoke-test regressions
automatically; they use local fixtures with the scheduler disabled and do
not establish production connectivity to scientific sources.

- Import real CRO/vendor and readiness data through `/api/ops/*/import`
  once you have it (see `import_templates/`) - nothing in that layer
  populates itself.
- Rotate the default `caddtard`/`caddtard` Postgres credentials in
  `docker-compose.yml` before using it as a template for a real deployment;
  Render/Railway generate their own credentials automatically and don't use
  this file directly.
