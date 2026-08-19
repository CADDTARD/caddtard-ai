from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Gene
from app.schemas import GeneOut, GeneWithVariants

router = APIRouter(prefix="/api/genes", tags=["genes"])


@router.get("", response_model=list[GeneOut])
def list_genes(
    top3_only: bool = Query(False, description="Only return the 4 genes behind the top-3 selected programs"),
    status_filter: str | None = Query(None, alias="status", description="confirmed | unverified"),
    db: Session = Depends(get_db),
):
    stmt = select(Gene)
    if top3_only:
        stmt = stmt.where(Gene.in_top3.is_(True))
    if status_filter:
        stmt = stmt.where(Gene.status == status_filter)
    return db.scalars(stmt.order_by(Gene.symbol)).all()


@router.get("/{symbol}", response_model=GeneWithVariants)
def get_gene(symbol: str, db: Session = Depends(get_db)):
    gene = db.scalar(select(Gene).where(Gene.symbol == symbol.upper()))
    if gene is None:
        raise HTTPException(status_code=404, detail=f"Gene '{symbol}' not found")
    return gene
