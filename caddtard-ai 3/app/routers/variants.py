from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Gene, Variant
from app.schemas import VariantOut

router = APIRouter(prefix="/api/variants", tags=["variants"])


@router.get("", response_model=list[VariantOut])
def list_variants(
    gene: str | None = Query(None, description="Filter by gene symbol, e.g. ATP6V0A4"),
    db: Session = Depends(get_db),
):
    """Variant-level rows from the originally uploaded LOF data.xlsx, now queryable
    by gene instead of scrolling a spreadsheet. See /api/genes/{symbol} for the
    verified disease association each gene carries."""
    stmt = select(Variant).options(joinedload(Variant.gene))
    if gene:
        stmt = stmt.join(Gene).where(Gene.symbol == gene.upper())
    return db.scalars(stmt).all()
