"""
v3.0 Operational Layer API: CRO/vendor registry, studies, samples/chain of
custody, assay acceptance, cost tracking, go/no-go governance, and CMC/
nonclinical/regulatory readiness. Import endpoints accept raw CSV text
(matching the *_import_template.csv files in /import_templates) and use the
exact functions in app/ops_import.py - no separate "preview" logic that could
drift from what actually gets inserted.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_ops import (
    AssayAcceptanceCriterion,
    AssayAcceptanceEvaluation,
    ChainOfCustodyEvent,
    CroVendor,
    GoNoGoDecision,
    ReadinessRequirement,
    Sample,
    Study,
    StudyCost,
    StudyMilestone,
    VendorQuote,
)
from app.ops_import import (
    ImportError_,
    import_assay_acceptance,
    import_cro_vendors,
    import_readiness,
    import_samples,
    import_study_costs,
    import_vendor_quotes,
)
from app.ops_logic import (
    GoNoGoInput,
    budget_status_from_variance,
    compute_cost_variance_pct,
    compute_go_no_go,
    timeline_status_from_milestones,
)

router = APIRouter(prefix="/api/ops", tags=["operations"])


class CsvImportBody(BaseModel):
    csv_text: str
    source: str = "manual_upload"


# --- CRO / vendor registry -------------------------------------------------
@router.get("/vendors")
def list_vendors(db: Session = Depends(get_db)):
    return db.scalars(select(CroVendor)).all()


@router.post("/vendors/import")
def import_vendors(body: CsvImportBody, db: Session = Depends(get_db)):
    try:
        created = import_cro_vendors(db, body.csv_text, body.source)
        db.commit()
    except ImportError_ as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    return {"imported": len(created)}


@router.get("/vendors/{vendor_id}/quotes")
def list_quotes(vendor_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(VendorQuote).where(VendorQuote.vendor_id == vendor_id)).all()


@router.post("/quotes/import")
def import_quotes(body: CsvImportBody, db: Session = Depends(get_db)):
    vendors = db.scalars(select(CroVendor)).all()
    name_map = {v.name: v.id for v in vendors}
    try:
        created = import_vendor_quotes(db, body.csv_text, body.source, name_map)
        db.commit()
    except ImportError_ as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    return {"imported": len(created)}


@router.get("/quotes/compare")
def compare_quotes(study_type: str, db: Session = Depends(get_db)):
    """Straight ranking by price for a given study_type - the 'Quote
    Comparator' function. No scoring beyond what's on file."""
    quotes = db.scalars(select(VendorQuote).where(VendorQuote.study_type == study_type)).all()
    ranked = sorted(quotes, key=lambda q: q.price_usd)
    return [
        {"vendor_id": q.vendor_id, "price_usd": q.price_usd, "turnaround_days": q.turnaround_days, "quote_id": q.id}
        for q in ranked
    ]


# --- Studies -----------------------------------------------------------
@router.get("/studies")
def list_studies(db: Session = Depends(get_db)):
    return db.scalars(select(Study)).all()


@router.post("/studies")
def create_study(study: dict, db: Session = Depends(get_db)):
    s = Study(**{k: v for k, v in study.items() if k in Study.__table__.columns.keys()})
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.get("/studies/{study_id}")
def get_study(study_id: int, db: Session = Depends(get_db)):
    s = db.get(Study, study_id)
    if not s:
        raise HTTPException(404, "study not found")
    return s


# --- Samples / chain of custody ----------------------------------------
@router.post("/studies/{study_id}/samples/import")
def import_study_samples(study_id: int, body: CsvImportBody, db: Session = Depends(get_db)):
    if not db.get(Study, study_id):
        raise HTTPException(404, "study not found")
    try:
        created = import_samples(db, body.csv_text, body.source, study_id)
        for s in created:
            db.add(ChainOfCustodyEvent(sample_id=s.id, event_type="collected", to_custodian=s.current_custodian, location=s.current_location))
        db.commit()
    except ImportError_ as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    return {"imported": len(created)}


@router.post("/samples/{sample_id}/custody-events")
def add_custody_event(sample_id: int, event: dict, db: Session = Depends(get_db)):
    sample = db.get(Sample, sample_id)
    if not sample:
        raise HTTPException(404, "sample not found")
    ev = ChainOfCustodyEvent(
        sample_id=sample_id,
        event_type=event.get("event_type", "transferred"),
        from_custodian=sample.current_custodian,
        to_custodian=event.get("to_custodian", ""),
        location=event.get("location", sample.current_location),
        notes=event.get("notes", ""),
    )
    sample.current_custodian = ev.to_custodian or sample.current_custodian
    sample.current_location = ev.location or sample.current_location
    if event.get("status"):
        sample.status = event["status"]
    db.add(ev)
    db.commit()
    return {"sample_id": sample_id, "current_custodian": sample.current_custodian, "status": sample.status}


@router.get("/samples/{sample_id}/chain-of-custody")
def get_chain_of_custody(sample_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(ChainOfCustodyEvent).where(ChainOfCustodyEvent.sample_id == sample_id).order_by(ChainOfCustodyEvent.event_at)
    ).all()


# --- Assay acceptance ----------------------------------------------------
@router.post("/studies/{study_id}/assay-acceptance/import")
def import_assay_acceptance_route(study_id: int, body: CsvImportBody, db: Session = Depends(get_db)):
    if not db.get(Study, study_id):
        raise HTTPException(404, "study not found")
    try:
        created = import_assay_acceptance(db, body.csv_text, body.source, study_id)
        db.commit()
    except (ImportError_, ValueError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    return {"imported": len(created)}


@router.get("/studies/{study_id}/assay-acceptance")
def get_assay_acceptance(study_id: int, db: Session = Depends(get_db)):
    criteria = db.scalars(select(AssayAcceptanceCriterion).where(AssayAcceptanceCriterion.study_id == study_id)).all()
    out = []
    for c in criteria:
        evals = db.scalars(select(AssayAcceptanceEvaluation).where(AssayAcceptanceEvaluation.criterion_id == c.id)).all()
        out.append({"criterion": c, "evaluations": evals})
    return out


# --- Costs ---------------------------------------------------------------
@router.post("/studies/{study_id}/costs/import")
def import_costs(study_id: int, body: CsvImportBody, db: Session = Depends(get_db)):
    if not db.get(Study, study_id):
        raise HTTPException(404, "study not found")
    try:
        created = import_study_costs(db, body.csv_text, body.source, study_id)
        db.commit()
    except ImportError_ as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    return {"imported": len(created)}


@router.get("/studies/{study_id}/cost-summary")
def cost_summary(study_id: int, db: Session = Depends(get_db)):
    costs = db.scalars(select(StudyCost).where(StudyCost.study_id == study_id)).all()
    budgeted = sum(c.budgeted_usd for c in costs)
    actual = sum(c.actual_usd for c in costs)
    variance = compute_cost_variance_pct(budgeted, actual)
    return {
        "budgeted_usd": budgeted,
        "actual_usd": actual,
        "variance_pct": variance,
        "budget_status": budget_status_from_variance(variance),
        "line_items": len(costs),
    }


# --- Go/No-Go governance --------------------------------------------------
@router.post("/studies/{study_id}/go-no-go/compute")
def compute_go_no_go_route(study_id: int, db: Session = Depends(get_db)):
    study = db.get(Study, study_id)
    if not study:
        raise HTTPException(404, "study not found")

    evaluations = (
        db.query(AssayAcceptanceEvaluation)
        .join(AssayAcceptanceCriterion, AssayAcceptanceEvaluation.criterion_id == AssayAcceptanceCriterion.id)
        .filter(AssayAcceptanceCriterion.study_id == study_id)
        .all()
    )
    assay_pass_rate = (sum(1 for e in evaluations if e.result == "pass") / len(evaluations)) if evaluations else None

    costs = db.scalars(select(StudyCost).where(StudyCost.study_id == study_id)).all()
    budgeted = sum(c.budgeted_usd for c in costs)
    actual = sum(c.actual_usd for c in costs)
    budget_status = budget_status_from_variance(compute_cost_variance_pct(budgeted, actual))

    milestones = db.scalars(select(StudyMilestone).where(StudyMilestone.study_id == study_id)).all()
    timeline_status = timeline_status_from_milestones([m.status for m in milestones])

    result = compute_go_no_go(
        GoNoGoInput(
            measured_candidate_score=None,  # wired to the v2 scoring/hypothesis-confidence layer once a study links to a ScoringCandidate
            assay_pass_rate=assay_pass_rate,
            budget_status=budget_status,
            timeline_status=timeline_status,
        )
    )
    decision = GoNoGoDecision(
        study_id=study_id,
        system_recommendation=result.recommendation,
        system_rationale=result.rationale,
        system_assay_acceptance_pass_rate=assay_pass_rate,
        system_budget_status=budget_status,
        system_timeline_status=timeline_status,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


@router.post("/go-no-go/{decision_id}/review")
def review_go_no_go(decision_id: int, review: dict, db: Session = Depends(get_db)):
    """Human decision workflow: approve, reject, or defer a system-proposed
    recommendation. This endpoint is the only way human_decision changes -
    no code path sets it automatically."""
    d = db.get(GoNoGoDecision, decision_id)
    if not d:
        raise HTTPException(404, "decision not found")
    decision = review.get("human_decision")
    if decision not in ("approved", "rejected", "deferred"):
        raise HTTPException(422, "human_decision must be one of approved|rejected|deferred")
    from datetime import datetime, timezone

    d.human_decision = decision
    d.human_reviewer = review.get("human_reviewer", "")
    d.human_notes = review.get("human_notes", "")
    d.human_decision_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(d)
    return d


@router.get("/studies/{study_id}/go-no-go")
def list_go_no_go(study_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(GoNoGoDecision).where(GoNoGoDecision.study_id == study_id)).all()


# --- CMC / nonclinical / regulatory readiness -----------------------------
@router.post("/readiness/{category}/import")
def import_readiness_route(category: str, body: CsvImportBody, db: Session = Depends(get_db)):
    if category not in ("cmc", "nonclinical", "regulatory", "ind_cta"):
        raise HTTPException(422, "category must be one of cmc|nonclinical|regulatory|ind_cta")
    try:
        created = import_readiness(db, body.csv_text, body.source, category)
        db.commit()
    except ImportError_ as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    return {"imported": len(created)}


@router.get("/readiness/{candidate_slug}")
def get_readiness(candidate_slug: str, db: Session = Depends(get_db)):
    reqs = db.scalars(select(ReadinessRequirement).where(ReadinessRequirement.candidate_slug == candidate_slug)).all()
    by_category: dict[str, list] = {}
    for r in reqs:
        by_category.setdefault(r.category, []).append(r)
    summary = {}
    for cat, rows in by_category.items():
        counts = {}
        for r in rows:
            counts[r.evidence_status] = counts.get(r.evidence_status, 0) + 1
        summary[cat] = {"requirements": rows, "status_counts": counts}
    return summary
