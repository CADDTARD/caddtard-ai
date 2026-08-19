"""
Shared plumbing for every agent: each run gets an AgentRun row (audit trail),
each agent opens its own DB session (scheduler jobs run outside any HTTP
request, so they can't use the FastAPI `get_db` dependency), and every run is
wrapped so that a failed HTTP call to an external API is recorded as a
failed/partial run instead of crashing the scheduler thread.
"""
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import AgentRun

logger = logging.getLogger("caddtard.agents")


@contextmanager
def agent_run(db, agent_name: str, run_id: int | None, trigger: str):
    """Creates (scheduled) or reuses (manual, already inserted by the API) the
    AgentRun row, then finalizes it with status/summary/detail on exit."""
    if run_id is not None:
        run = db.get(AgentRun, run_id)
    else:
        run = None

    if run is None:
        run = AgentRun(agent_name=agent_name, trigger=trigger, status="running")
        db.add(run)
        db.commit()
        db.refresh(run)

    result = {"summary": "", "detail": {}}
    try:
        yield result
        run.status = "success"
        run.summary = result["summary"] or "Completed"
    except Exception as exc:  # noqa: BLE001 - agents must never crash the scheduler
        logger.exception("Agent '%s' failed", agent_name)
        run.status = "error"
        run.summary = f"{type(exc).__name__}: {exc}"
        result["detail"].setdefault("error", str(exc))
    finally:
        run.finished_at = datetime.now(timezone.utc)
        run.detail_json = json.dumps(result["detail"], default=str)[:8000]
        db.add(run)
        db.commit()


def with_session():
    return SessionLocal()
