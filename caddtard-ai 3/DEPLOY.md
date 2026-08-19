# Deploying CADDTARD AI so it actually runs continuously

Everything in this repo was written and verified inside a sandbox with no
outbound access to PyPI and no persistent public hostname (see
`ARCHITECTURE.md`'s "Continuous operation" section) - so "runs continuously"
could only be proven as code + logic in that environment, not as a live
deployment. This file is the concrete, real path to making it one.

The app is a standard Docker Compose stack (`api` + `db`), so it deploys to
any container host. Two free-tier-friendly options below.

## Option A — Render

Render's MCP connector (`mcp.render.com`) can drive this whole flow from
inside a chat session once connected - `create_postgres`, `create_web_service`,
and `get_deploy`/`get_metrics` cover the steps below without leaving the chat.

Manual steps (same result):

1. Push this repo to a GitHub/GitLab repo Render can read.
2. **New > PostgreSQL** on Render. Note the internal connection string.
3. **New > Web Service**, point it at the repo, Docker runtime (it will use
   the included `Dockerfile`).
4. Environment variables:
   - `DATABASE_URL` = the Postgres internal connection string from step 2
     (Render's string is `postgresql://...`; SQLAlchemy needs the
     `postgresql+psycopg2://` prefix - swap it)
   - `CORS_ORIGINS` = your Render service's `*.onrender.com` URL
   - `AGENTS_ENABLED` = `true`
   - `PATENTSVIEW_API_KEY` = optional, see `.env.example`
5. Health check path: `/health`
6. Deploy. The scheduler starts in `main.py`'s FastAPI lifespan handler on
   boot and keeps running for as long as the Render service is up - Render's
   free web services sleep after inactivity, so a paid instance (or Render's
   Cron Jobs hitting `/health` periodically) is what makes "continuous"
   literally true rather than "continuous while awake."

## Option B — Railway

Railway's MCP connector (`mcp.railway.com`) exposes `create-project`,
`deploy-artifact`, `get-logs`, `get-status` directly.

Manual steps:

1. **New Project > Deploy from GitHub repo**.
2. **New > Database > PostgreSQL** in the same project (Railway wires
   `DATABASE_URL` into other services automatically if you reference it as
   `${{Postgres.DATABASE_URL}}`; adjust the scheme prefix to
   `postgresql+psycopg2://` as above).
3. Set the same environment variables as the Render list above.
4. Railway services don't sleep on the Hobby plan the way Render's free tier
   does, which matters for a scheduler-driven app like this one.

## After either deploy

- Confirm the scheduler actually started: `GET /api/agents?status=implemented`
  should show 20 rows, then check `GET /api/agents/{key}/latest` after a few
  minutes for a handful of them - a `success` status with a real
  `finished_at` timestamp is the proof this is genuinely polling live data on
  its own, not just responding to requests.
- Import real CRO/vendor and readiness data through `/api/ops/*/import`
  once you have it (see `import_templates/`) - nothing in that layer
  populates itself.
- Rotate the default `caddtard`/`caddtard` Postgres credentials in
  `docker-compose.yml` before using it as a template for a real deployment;
  Render/Railway generate their own credentials automatically and don't use
  this file directly.
