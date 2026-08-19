from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.registry import AGENT_FUNCTIONS
from app.database import get_db
from app.models import AgentDefinition, AgentRun
from app.schemas import AgentDefinitionOut, AgentRunDetailOut, AgentRunOut

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentDefinitionOut])
def list_agents(
    division: str | None = Query(None, description="e.g. Genomics, Disease Biology, Therapeutics, AI Science, Development, Evidence & Infrastructure"),
    status_filter: str | None = Query(None, alias="status", description="implemented | planned"),
    db: Session = Depends(get_db),
):
    """The full ~50-agent taxonomy across all divisions from the architecture
    spec. 'implemented' rows have a real function wired to a live external
    source and a scheduled interval; 'planned' rows are reserved slots with a
    defined interface, not yet backed by code. See /api/sources for the
    underlying data sources each implemented agent calls."""
    stmt = select(AgentDefinition)
    if division:
        stmt = stmt.where(AgentDefinition.division == division)
    if status_filter:
        stmt = stmt.where(AgentDefinition.status == status_filter)
    definitions = db.scalars(stmt.order_by(AgentDefinition.division, AgentDefinition.name)).all()

    out = []
    for definition in definitions:
        last_run = None
        if definition.status == "implemented":
            last_run = db.scalar(
                select(AgentRun).where(AgentRun.agent_name == definition.key).order_by(AgentRun.started_at.desc())
            )
        out.append(
            AgentDefinitionOut(
                key=definition.key,
                name=definition.name,
                division=definition.division,
                description=definition.description,
                status=definition.status,
                interval_minutes=definition.interval_minutes,
                last_run=AgentRunOut.model_validate(last_run) if last_run else None,
            )
        )
    return out


@router.get("/divisions", response_model=list[str])
def list_divisions(db: Session = Depends(get_db)):
    rows = db.scalars(select(AgentDefinition.division).distinct().order_by(AgentDefinition.division)).all()
    return list(rows)


def _get_definition_or_404(key: str, db: Session) -> AgentDefinition:
    definition = db.scalar(select(AgentDefinition).where(AgentDefinition.key == key))
    if definition is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{key}'")
    return definition


@router.get("/{key}/runs", response_model=list[AgentRunOut])
def agent_run_history(key: str, limit: int = 20, db: Session = Depends(get_db)):
    _get_definition_or_404(key, db)
    stmt = select(AgentRun).where(AgentRun.agent_name == key).order_by(AgentRun.started_at.desc()).limit(limit)
    return db.scalars(stmt).all()


@router.get("/{key}/latest", response_model=AgentRunDetailOut)
def agent_latest_run(key: str, db: Session = Depends(get_db)):
    _get_definition_or_404(key, db)
    run = db.scalar(select(AgentRun).where(AgentRun.agent_name == key).order_by(AgentRun.started_at.desc()))
    if run is None:
        raise HTTPException(status_code=404, detail=f"Agent '{key}' has not run yet")
    return run


@router.post("/{key}/run", response_model=AgentRunOut, status_code=202)
def trigger_agent(key: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Manually trigger an implemented agent immediately, outside its
    schedule. Runs as a FastAPI background task so the HTTP response returns
    right away (202 Accepted); poll /api/agents/{key}/latest for the result.
    Returns 409 for a 'planned' agent - there's no function to run yet."""
    definition = _get_definition_or_404(key, db)
    if definition.status != "implemented" or key not in AGENT_FUNCTIONS:
        raise HTTPException(status_code=409, detail=f"Agent '{key}' is not implemented yet (status={definition.status})")

    pending = AgentRun(agent_name=key, status="running", trigger="manual", summary="Queued")
    db.add(pending)
    db.commit()
    db.refresh(pending)

    background_tasks.add_task(AGENT_FUNCTIONS[key], pending.id, "manual")
    return pending
