"""Read-only, evidence-graded V-ATPase compound landscape API."""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Compound
from app.schemas import CompoundOut, CompoundSummaryOut

router = APIRouter(prefix="/api/compounds", tags=["compound-landscape"])


def _out(compound: Compound) -> CompoundOut:
    try:
        evidence = json.loads(compound.evidence_json or "[]")
    except json.JSONDecodeError:
        evidence = []
    return CompoundOut(
        id=compound.id,
        slug=compound.slug,
        name=compound.name,
        tier=compound.tier,
        role=compound.role,
        verification_status=compound.verification_status,
        identity_verified=compound.identity_verified,
        mechanism_verified=compound.mechanism_verified,
        chemical_class=compound.chemical_class,
        cas_number=compound.cas_number,
        molecular_formula=compound.molecular_formula,
        molecular_weight=compound.molecular_weight,
        pubchem_cid=compound.pubchem_cid,
        target_site=compound.target_site,
        potency=compound.potency,
        development_status=compound.development_status,
        availability_note=compound.availability_note,
        platform_fit=compound.platform_fit,
        caveat=compound.caveat,
        evidence=evidence,
        source_report=compound.source_report,
        reviewed_at=compound.reviewed_at,
    )


@router.get("/summary", response_model=CompoundSummaryOut)
def summary(db: Session = Depends(get_db)):
    rows = db.scalars(select(Compound)).all()
    return CompoundSummaryOut(
        total=len(rows),
        verified=sum(c.verification_status == "verified" for c in rows),
        partial=sum(c.verification_status == "partial" for c in rows),
        unverified=sum(c.verification_status == "unverified" for c in rows),
        direct_inhibitors=sum(c.role == "direct_inhibitor" for c in rows),
        comparators=sum(c.role == "comparator" for c in rows),
        identity_verified=sum(c.identity_verified for c in rows),
        mechanism_verified=sum(c.mechanism_verified for c in rows),
        fto_cleared=0,
    )


@router.get("", response_model=list[CompoundOut])
def list_compounds(
    tier: str | None = Query(None, description="A, B, C, or appendix"),
    role: str | None = Query(None, description="direct_inhibitor, pathway_adjacent, comparator, benchmark, or thin_data"),
    verification: str | None = Query(None, description="verified, partial, or unverified"),
    q: str | None = Query(None, min_length=1, max_length=80),
    db: Session = Depends(get_db),
):
    stmt = select(Compound)
    if tier:
        stmt = stmt.where(Compound.tier == tier)
    if role:
        stmt = stmt.where(Compound.role == role)
    if verification:
        stmt = stmt.where(Compound.verification_status == verification)
    if q:
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(
            func.lower(Compound.name).like(pattern),
            func.lower(Compound.chemical_class).like(pattern),
            func.lower(Compound.target_site).like(pattern),
        ))
    tier_order = {"A": 0, "B": 1, "C": 2, "appendix": 3}
    rows = db.scalars(stmt.order_by(Compound.name)).all()
    rows = sorted(rows, key=lambda c: (tier_order.get(c.tier, 9), c.name.lower()))
    return [_out(row) for row in rows]


@router.get("/{slug}", response_model=CompoundOut)
def get_compound(slug: str, db: Session = Depends(get_db)):
    compound = db.scalar(select(Compound).where(Compound.slug == slug))
    if compound is None:
        raise HTTPException(status_code=404, detail=f"Compound '{slug}' not found")
    return _out(compound)

