from fastapi import APIRouter, Response, status

from app.config import get_settings
from app.database import db_is_ready
from app.database import SessionLocal
from app.models import AgentDefinition
from app.schemas import HealthOut, ReadinessOut

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health", response_model=HealthOut)
def liveness():
    """Liveness probe - no dependencies checked. If this fails, the process is dead."""
    return HealthOut(status="ok", app=settings.app_name, version=settings.app_version)


@router.get("/health/ready", response_model=ReadinessOut)
def readiness(response: Response):
    """Readiness probe - checks the database connection and the scheduler state.
    Returns HTTP 503 (not 200) when not ready, so orchestrators/load balancers
    correctly stop routing traffic here."""
    from app.agents.scheduler import scheduler_is_running, scheduler_job_count

    db_ok = db_is_ready()
    sched_ok = scheduler_is_running() if settings.agents_enabled else True
    expected_jobs = 0
    if db_ok and settings.agents_enabled:
        db = SessionLocal()
        try:
            expected_jobs = db.query(AgentDefinition).filter(AgentDefinition.status == "implemented").count()
        finally:
            db.close()
    registered_jobs = scheduler_job_count() if settings.agents_enabled else 0
    jobs_ok = (registered_jobs == expected_jobs) if settings.agents_enabled else True
    ready = db_ok and sched_ok and jobs_ok
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessOut(
        status="ready" if ready else "not_ready",
        database=db_ok,
        scheduler_running=sched_ok,
        registered_jobs=registered_jobs,
        expected_jobs=expected_jobs,
    )
