from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ScoringCandidate
from app.schemas import ScoringOut

router = APIRouter(prefix="/api/scoring", tags=["scoring"])


@router.get("", response_model=list[ScoringOut])
def list_scoring(db: Session = Depends(get_db)):
    """Full prioritization rubric: 10 program candidates scored 1-5 on commercial
    success, patient numbers, CMC probability and overall feasibility, sorted by
    composite score. See /api/candidates for the 3 that were selected."""
    stmt = select(ScoringCandidate).order_by(ScoringCandidate.composite.desc())
    return db.scalars(stmt).all()
