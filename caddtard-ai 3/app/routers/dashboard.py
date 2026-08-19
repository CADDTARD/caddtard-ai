"""
Layer 6 - Executive Dashboard. Aggregates real data from every other layer
into the summary widgets the architecture spec asks for (project health,
evidence strength, experimental status, portfolio prioritization, ...)
rather than introducing a separate "dashboard database" - this router is a
read-only view over Layers 1-5.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Candidate, ChecklistItem, Experiment, Hypothesis, HypothesisStep, ScoringCandidate, TimelineItem
from app.schemas import ProjectHealthOut

router = APIRouter(prefix="/api/dashboard", tags=["executive-dashboard"])

# Maps a Candidate.slug to its matching ScoringCandidate.program label
# (the two tables are seeded from the same research pass but keyed differently -
# see app/seed_data.py CANDIDATES vs SCORING).
SCORING_PROGRAM_BY_SLUG = {
    "drta": "Distal renal tubular acidosis (ATP6V0A4 + ATP6V1B1)",
    "atp6v0c": "Neurodevelopmental disorder with epilepsy (ATP6V0C)",
    "tcirg1": "Infantile malignant osteopetrosis (TCIRG1)",
}

# Known, documented risk flags per candidate (see Candidate.risks free text and
# the prior report's risk-agent section) - kept as a small static count here
# rather than parsed from free text, so the number is stable and traceable.
KNOWN_RISK_FLAG_COUNT = {"drta": 1, "atp6v0c": 1, "tcirg1": 2}


@router.get("/health/{slug}", response_model=ProjectHealthOut)
def project_health(slug: str, db: Session = Depends(get_db)):
    candidate = db.scalar(select(Candidate).where(Candidate.slug == slug))
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"Candidate '{slug}' not found")

    checklist = db.scalars(select(ChecklistItem).where(ChecklistItem.candidate_slug == slug)).all()
    completion = (sum(1 for c in checklist if c.checked) / len(checklist) * 100) if checklist else 0.0

    hyps = db.scalars(select(Hypothesis).where(Hypothesis.candidate_slug == slug)).all()
    hyp_ids = [h.id for h in hyps]
    steps = db.scalars(select(HypothesisStep).where(HypothesisStep.hypothesis_id.in_(hyp_ids))).all() if hyp_ids else []
    avg_conf = (sum(s.confidence for s in steps) / len(steps)) if steps else 0.0

    experiments = db.scalars(select(Experiment).where(Experiment.candidate_slug == slug)).all()
    in_progress = sum(1 for e in experiments if e.status == "in_progress")
    completed = sum(1 for e in experiments if e.status == "completed")

    milestone_count = len(db.scalars(select(TimelineItem).where(TimelineItem.candidate_id == candidate.id)).all())

    program_name = SCORING_PROGRAM_BY_SLUG.get(slug, "")
    scoring = db.scalar(select(ScoringCandidate).where(ScoringCandidate.program == program_name))

    return ProjectHealthOut(
        candidate_slug=slug,
        candidate_name=candidate.name,
        checklist_completion_pct=round(completion, 1),
        avg_hypothesis_confidence=round(avg_conf, 3),
        open_high_risk_flags=KNOWN_RISK_FLAG_COUNT.get(slug, 0),
        experiments_in_progress=in_progress,
        experiments_completed=completed,
        milestones_total=milestone_count,
        scoring_composite=scoring.composite if scoring else 0.0,
    )


@router.get("/health", response_model=list[ProjectHealthOut])
def portfolio_health(db: Session = Depends(get_db)):
    """All 3 candidates' health at once - the portfolio prioritization view."""
    candidates = db.scalars(select(Candidate)).all()
    return [project_health(c.slug, db) for c in candidates]
