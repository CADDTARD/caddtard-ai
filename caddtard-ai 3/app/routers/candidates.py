from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Candidate, CostSummary
from app.schemas import CandidateDetailOut, CandidateOut, CostItemOut, CostSummaryOut, TimelineItemOut

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.get("", response_model=list[CandidateOut])
def list_candidates(db: Session = Depends(get_db)):
    """The 3 program candidates selected by the prioritization rubric."""
    return db.scalars(select(Candidate).order_by(Candidate.name)).all()


@router.get("/{slug}", response_model=CandidateDetailOut)
def get_candidate(slug: str, db: Session = Depends(get_db)):
    candidate = db.scalar(
        select(Candidate)
        .where(Candidate.slug == slug)
        .options(joinedload(Candidate.timeline_items), joinedload(Candidate.cost_items))
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"Candidate '{slug}' not found")

    summary = db.scalar(select(CostSummary).where(CostSummary.candidate_slug == slug))
    ordered_timeline = sorted(candidate.timeline_items, key=lambda t: t.sort_order)

    return CandidateDetailOut(
        slug=candidate.slug,
        name=candidate.name,
        genes=candidate.genes,
        uniprot=candidate.uniprot,
        organ=candidate.organ,
        inheritance=candidate.inheritance,
        omim=candidate.omim,
        mechanism=candidate.mechanism,
        soc=candidate.soc,
        modality=candidate.modality,
        biomarkers=candidate.biomarkers,
        commercial_precedent=candidate.commercial_precedent,
        risks=candidate.risks,
        timeline=[TimelineItemOut.model_validate(t) for t in ordered_timeline],
        cost_items=[CostItemOut.model_validate(c) for c in candidate.cost_items],
        cost_summary=CostSummaryOut.model_validate(summary) if summary else None,
    )
