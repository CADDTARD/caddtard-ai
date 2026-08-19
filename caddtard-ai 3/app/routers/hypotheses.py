import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Hypothesis
from app.schemas import HypothesisOut, HypothesisStepOut, SupportingPaper

router = APIRouter(prefix="/api/hypotheses", tags=["reasoning-engine"])


def _to_out(h: Hypothesis) -> HypothesisOut:
    steps = sorted(h.steps, key=lambda s: s.sort_order)
    step_outs = [
        HypothesisStepOut(
            id=s.id,
            sort_order=s.sort_order,
            from_label=s.from_label,
            to_label=s.to_label,
            supporting_papers=[SupportingPaper(**p) for p in json.loads(s.supporting_papers_json or "[]")],
            confidence=s.confidence,
            conflicting_evidence=s.conflicting_evidence,
            experimental_status=s.experimental_status,
            recommended_next_experiment=s.recommended_next_experiment,
        )
        for s in steps
    ]
    overall = sum(s.confidence for s in step_outs) / len(step_outs) if step_outs else 0.0
    return HypothesisOut(
        id=h.id, number=h.number, title=h.title, candidate_slug=h.candidate_slug,
        gene_symbol=h.gene_symbol, status=h.status, overall_confidence=round(overall, 3),
        steps=step_outs,
    )


@router.get("", response_model=list[HypothesisOut])
def list_hypotheses(
    candidate: str | None = Query(None, description="Filter by candidate slug"),
    gene: str | None = Query(None, description="Filter by gene symbol"),
    db: Session = Depends(get_db),
):
    """Layer 4 - Scientific Reasoning Engine. Each hypothesis is an explicit,
    evidence-graded causal chain (mechanism -> ... -> disease phenotype), not
    a free-text answer - every edge carries its own confidence, supporting
    papers, conflicting evidence, experimental status, and recommended next
    experiment, and is meant to be revised as new evidence arrives."""
    stmt = select(Hypothesis).options(joinedload(Hypothesis.steps)).order_by(Hypothesis.number)
    if candidate:
        stmt = stmt.where(Hypothesis.candidate_slug == candidate)
    if gene:
        stmt = stmt.where(Hypothesis.gene_symbol == gene.upper())
    hypotheses = db.scalars(stmt).unique().all()
    return [_to_out(h) for h in hypotheses]


@router.get("/{number}", response_model=HypothesisOut)
def get_hypothesis(number: int, db: Session = Depends(get_db)):
    h = db.scalar(select(Hypothesis).where(Hypothesis.number == number).options(joinedload(Hypothesis.steps)))
    if h is None:
        raise HTTPException(status_code=404, detail=f"Hypothesis {number} not found")
    return _to_out(h)
