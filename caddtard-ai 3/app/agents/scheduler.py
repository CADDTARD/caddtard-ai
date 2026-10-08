"""
APScheduler-backed background job runner. Started once from main.py's FastAPI
lifespan handler (after seeding, so agent_definitions rows exist), stopped
cleanly on shutdown. One job per agent whose AgentDefinition.status ==
"implemented", using that row's own interval_minutes. Scheduled and manually
triggered runs call the exact same function (see routers/agents.py).
"""
import datetime as dt
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.agents.registry import AGENT_FUNCTIONS
from app.config import get_settings
from app.database import SessionLocal
from app.models import AgentDefinition

logger = logging.getLogger("caddtard.scheduler")

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    settings = get_settings()
    if not settings.agents_enabled:
        logger.info("AGENTS_ENABLED=false - scheduler not started.")
        return None

    db = SessionLocal()
    try:
        implemented = db.scalars(
            select(AgentDefinition).where(AgentDefinition.status == "implemented")
        ).all()
    finally:
        db.close()

    scheduler = BackgroundScheduler(
        timezone="UTC",
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": settings.agent_misfire_grace_seconds,
        },
    )
    now = dt.datetime.now(dt.timezone.utc)
    staggered = 0
    for definition in implemented:
        fn = AGENT_FUNCTIONS.get(definition.key)
        if fn is None:
            logger.warning("AgentDefinition '%s' marked implemented but has no registered function - skipping.", definition.key)
            continue
        interval = definition.interval_minutes or settings.default_agent_interval_minutes
        scheduler.add_job(
            fn,
            "interval",
            minutes=interval,
            id=f"agent-{definition.key}",
            kwargs={"run_id": None, "trigger": "scheduled"},
            next_run_time=now + dt.timedelta(
                seconds=settings.agent_initial_delay_seconds + staggered * settings.agent_stagger_seconds
            ),
            replace_existing=True,
        )
        staggered += 1

    scheduler.start()
    _scheduler = scheduler
    logger.info("Scheduler started with %d agent jobs (%d agent_definitions were 'implemented').", staggered, len(implemented))
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def scheduler_is_running() -> bool:
    return _scheduler is not None and _scheduler.running


def scheduler_job_count() -> int:
    if not scheduler_is_running():
        return 0
    return len(_scheduler.get_jobs())
