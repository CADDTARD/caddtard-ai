"""Read-only proof-of-concept mission-control payload."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AgentDefinition, AgentRun
from app.poc_data import (
    BIOLOGY_CHAIN,
    DEVELOPMENT_TIERS,
    EVIDENCE_BOUNDARY,
    EXECUTION_COPILOTS,
    EXPERIMENTAL_GROUPS,
    FUNDING_MILESTONES,
    GO_NO_GO_GATES,
    PROGRAM,
    RIGOR_LOCKS,
    VERIFICATION_SOURCES,
)

router = APIRouter(prefix="/api/poc", tags=["proof-of-concept"])


@router.get("")
def poc_mission_control(db: Session = Depends(get_db)):
    """Return the validated POC plan plus current scheduled-agent evidence state.

    This endpoint never triggers an agent and never converts a scheduled run
    into an experimental result.  Gate status remains planned until qualified
    assay data are ingested through the laboratory operating system.
    """
    mapped_keys = sorted({key for copilot in EXECUTION_COPILOTS for key in copilot["agent_keys"]})
    definitions = {
        row.key: row
        for row in db.scalars(select(AgentDefinition).where(AgentDefinition.key.in_(mapped_keys))).all()
    } if mapped_keys else {}

    latest_runs = {}
    for key in mapped_keys:
        latest_runs[key] = db.scalar(
            select(AgentRun).where(AgentRun.agent_name == key).order_by(AgentRun.started_at.desc())
        )

    copilots = []
    for item in EXECUTION_COPILOTS:
        sources = []
        for key in item["agent_keys"]:
            definition = definitions.get(key)
            run = latest_runs.get(key)
            sources.append({
                "key": key,
                "name": definition.name if definition else key.replace("_", " ").title(),
                "implemented": bool(definition and definition.status == "implemented"),
                "latest_status": run.status if run else None,
                "latest_finished_at": run.finished_at if run else None,
            })
        implemented = [source for source in sources if source["implemented"]]
        successful = [source for source in sources if source["latest_status"] == "success"]
        if successful:
            state = "live_evidence"
        elif implemented:
            state = "connected_waiting"
        else:
            state = "interface_ready"
        copilots.append({**item, "state": state, "sources": sources})

    return {
        "generated_at": datetime.now(timezone.utc),
        "program": PROGRAM,
        "evidence_boundary": EVIDENCE_BOUNDARY,
        "counts": {
            "biology_steps": len(BIOLOGY_CHAIN),
            "experimental_groups": len(EXPERIMENTAL_GROUPS),
            "development_tiers": len(DEVELOPMENT_TIERS),
            "go_no_go_gates": len(GO_NO_GO_GATES),
            "validated_gates": 0,
            "copilot_interfaces": len(copilots),
            "live_copilots": sum(copilot["state"] == "live_evidence" for copilot in copilots),
        },
        "biology_chain": BIOLOGY_CHAIN,
        "experimental_groups": EXPERIMENTAL_GROUPS,
        "development_tiers": DEVELOPMENT_TIERS,
        "go_no_go_gates": [{**gate, "status": "planned"} for gate in GO_NO_GO_GATES],
        "rigor_locks": RIGOR_LOCKS,
        "funding_milestones": FUNDING_MILESTONES,
        "execution_copilots": copilots,
        "verification_sources": VERIFICATION_SOURCES,
        "funding_truth": {
            "headline": "Design ready. Evidence generation next.",
            "current_state": "The decision framework is complete; no experimental gate is represented as validated.",
            "investment_case": (
                "A fundable package emerges when variant-specific mechanism, cellular target engagement, human-neuron "
                "functional rescue, safety and independent replication fill these gates."
            ),
        },
    }

