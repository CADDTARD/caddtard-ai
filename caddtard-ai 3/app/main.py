"""
CADDTARD AI v3.1 MVP - FastAPI application entrypoint.

Run directly:      uvicorn app.main:app --reload
Run via Docker:     see Dockerfile / docker-compose.yml
Interactive docs:   http://localhost:8000/docs
Dashboard:          http://localhost:8000/
"""
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.agents.scheduler import start_scheduler, stop_scheduler
from app.config import get_settings
from app.routers import (
    agents,
    candidates,
    checklist,
    dashboard,
    genes,
    graph,
    health,
    hypotheses,
    lab,
    ops,
    scoring,
    sources,
    variants,
)
from app.seed import run_seed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("caddtard.main")

settings = get_settings()
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    run_seed()
    start_scheduler()
    yield
    logger.info("Shutting down scheduler...")
    stop_scheduler()


app = FastAPI(
    title="CADDTARD AI",
    description=(
        "Computer-Aided Drug Design Targeting Rare Disease - V-ATPase loss-of-function program. "
        "Real API, persistent database, and scheduled monitoring agents behind the CADDTARD dashboard."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)


@app.middleware("http")
async def enforce_public_read_only(request: Request, call_next):
    """Reject public HTTP mutations when running as a read-only demo.

    This protects lab, CRO import, checklist, and manual agent-run endpoints
    without disabling the in-process scheduler's database writes.
    """
    safe_method = request.method in {"GET", "HEAD", "OPTIONS"}
    agent_trigger = (
        request.method == "POST"
        and request.url.path.startswith("/api/agents/")
        and request.url.path.endswith("/run")
        and request.url.path.count("/") == 4
    )
    supplied_token = request.headers.get("x-admin-token", "")
    authorized_trigger = bool(
        agent_trigger
        and settings.admin_trigger_token
        and supplied_token
        and secrets.compare_digest(supplied_token, settings.admin_trigger_token)
    )
    if settings.public_read_only and not safe_method and not authorized_trigger:
        return JSONResponse(
            status_code=403,
            content={"detail": "This public deployment is read-only; an admin token is required for manual agent triggers."},
        )
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(genes.router)
app.include_router(variants.router)
app.include_router(scoring.router)
app.include_router(candidates.router)
app.include_router(checklist.router)
app.include_router(agents.router)
app.include_router(sources.router)
app.include_router(graph.router)
app.include_router(hypotheses.router)
app.include_router(lab.router)
app.include_router(dashboard.router)
app.include_router(ops.router)

# Mounted last so it acts as a catch-all for the browser dashboard without
# shadowing any /api/* or /health route registered above.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="dashboard")
