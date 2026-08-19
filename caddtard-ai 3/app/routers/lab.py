"""
Layer 5 - Laboratory Operating System. Real CRUD against Experiment,
Protocol, ReagentItem, NotebookEntry, AssayResult - the actual instrument/ELN/
LIMS integrations described in the architecture spec (sequencing pipelines,
microscopy, flow cytometry, etc.) are not connected to any real hardware in
this environment (there is no lab), so this layer captures the same records
those systems would produce, entered directly through the API, and the
`assay_type` enum matches the instrument categories named in the spec.

The "AI recommends the next experiment" requirement is implemented literally:
/api/lab/recommendations surfaces the recommended_next_experiment field from
every open (non-validated) hypothesis step in the reasoning engine (Layer 4),
rather than a black-box ML suggestion - every recommendation is traceable
back to the specific hypothesis and evidence gap that generated it.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AssayResult, Experiment, Hypothesis, HypothesisStep, NotebookEntry, Protocol, ReagentItem
from app.schemas import (
    AssayResultCreate,
    AssayResultOut,
    ExperimentCreate,
    ExperimentOut,
    ExperimentUpdate,
    NextExperimentSuggestion,
    NotebookEntryCreate,
    NotebookEntryOut,
    ProtocolCreate,
    ProtocolOut,
    ReagentItemCreate,
    ReagentItemOut,
)
from app.schemas import HypothesisStepOut, SupportingPaper

router = APIRouter(prefix="/api/lab", tags=["laboratory-os"])


@router.get("/experiments", response_model=list[ExperimentOut])
def list_experiments(candidate: str | None = None, status_filter: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Experiment)
    if candidate:
        stmt = stmt.where(Experiment.candidate_slug == candidate)
    if status_filter:
        stmt = stmt.where(Experiment.status == status_filter)
    return db.scalars(stmt.order_by(Experiment.created_at.desc())).all()


@router.post("/experiments", response_model=ExperimentOut, status_code=201)
def create_experiment(body: ExperimentCreate, db: Session = Depends(get_db)):
    exp = Experiment(**body.model_dump())
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


@router.get("/experiments/{experiment_id}", response_model=ExperimentOut)
def get_experiment(experiment_id: int, db: Session = Depends(get_db)):
    exp = db.get(Experiment, experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found")
    return exp


@router.patch("/experiments/{experiment_id}", response_model=ExperimentOut)
def update_experiment(experiment_id: int, body: ExperimentUpdate, db: Session = Depends(get_db)):
    exp = db.get(Experiment, experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(exp, field, value)
    db.commit()
    db.refresh(exp)
    return exp


@router.post("/experiments/{experiment_id}/protocols", response_model=ProtocolOut, status_code=201)
def add_protocol(experiment_id: int, body: ProtocolCreate, db: Session = Depends(get_db)):
    if db.get(Experiment, experiment_id) is None:
        raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found")
    protocol = Protocol(experiment_id=experiment_id, **body.model_dump())
    db.add(protocol)
    db.commit()
    db.refresh(protocol)
    return protocol


@router.post("/experiments/{experiment_id}/notebook", response_model=NotebookEntryOut, status_code=201)
def add_notebook_entry(experiment_id: int, body: NotebookEntryCreate, db: Session = Depends(get_db)):
    if db.get(Experiment, experiment_id) is None:
        raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found")
    entry = NotebookEntry(experiment_id=experiment_id, **body.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/experiments/{experiment_id}/notebook", response_model=list[NotebookEntryOut])
def list_notebook_entries(experiment_id: int, db: Session = Depends(get_db)):
    stmt = select(NotebookEntry).where(NotebookEntry.experiment_id == experiment_id).order_by(NotebookEntry.entry_date.desc())
    return db.scalars(stmt).all()


def _assay_out(a: AssayResult) -> AssayResultOut:
    return AssayResultOut(
        id=a.id, experiment_id=a.experiment_id, assay_type=a.assay_type, summary=a.summary,
        data=json.loads(a.data_json or "{}"), file_ref=a.file_ref, recorded_at=a.recorded_at,
    )


@router.post("/experiments/{experiment_id}/results", response_model=AssayResultOut, status_code=201)
def add_assay_result(experiment_id: int, body: AssayResultCreate, db: Session = Depends(get_db)):
    if db.get(Experiment, experiment_id) is None:
        raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found")
    result = AssayResult(
        experiment_id=experiment_id, assay_type=body.assay_type, summary=body.summary,
        data_json=json.dumps(body.data), file_ref=body.file_ref,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return _assay_out(result)


@router.get("/experiments/{experiment_id}/results", response_model=list[AssayResultOut])
def list_assay_results(experiment_id: int, db: Session = Depends(get_db)):
    stmt = select(AssayResult).where(AssayResult.experiment_id == experiment_id).order_by(AssayResult.recorded_at.desc())
    return [_assay_out(a) for a in db.scalars(stmt).all()]


@router.get("/reagents", response_model=list[ReagentItemOut])
def list_reagents(low_stock_only: bool = False, db: Session = Depends(get_db)):
    items = db.scalars(select(ReagentItem).order_by(ReagentItem.name)).all()
    if low_stock_only:
        items = [i for i in items if i.quantity <= i.reorder_threshold]
    return items


@router.post("/reagents", response_model=ReagentItemOut, status_code=201)
def add_reagent(body: ReagentItemCreate, db: Session = Depends(get_db)):
    item = ReagentItem(**body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/recommendations", response_model=list[NextExperimentSuggestion])
def next_experiment_recommendations(candidate: str | None = None, db: Session = Depends(get_db)):
    """The AI-recommends-the-next-experiment requirement, implemented as a
    direct, traceable readout of the reasoning engine: every hypothesis step
    that is not yet 'validated' and has a recommended_next_experiment carries
    an open evidence gap - these are surfaced here, ranked by ascending
    confidence (weakest-evidenced links first)."""
    stmt = (
        select(HypothesisStep, Hypothesis)
        .join(Hypothesis, HypothesisStep.hypothesis_id == Hypothesis.id)
        .where(HypothesisStep.experimental_status != "validated")
        .where(HypothesisStep.recommended_next_experiment != "")
    )
    if candidate:
        stmt = stmt.where(Hypothesis.candidate_slug == candidate)

    rows = db.execute(stmt).all()
    rows.sort(key=lambda r: r[0].confidence)

    out = []
    for step, hyp in rows:
        out.append(NextExperimentSuggestion(
            hypothesis_number=hyp.number,
            hypothesis_title=hyp.title,
            step=HypothesisStepOut(
                id=step.id, sort_order=step.sort_order, from_label=step.from_label, to_label=step.to_label,
                supporting_papers=[SupportingPaper(**p) for p in json.loads(step.supporting_papers_json or "[]")],
                confidence=step.confidence, conflicting_evidence=step.conflicting_evidence,
                experimental_status=step.experimental_status,
                recommended_next_experiment=step.recommended_next_experiment,
            ),
            reason=f"Confidence {step.confidence:.2f} and status '{step.experimental_status}' on the "
                   f"'{step.from_label} -> {step.to_label}' link is the weakest-evidenced part of Hypothesis {hyp.number}.",
        ))
    return out
