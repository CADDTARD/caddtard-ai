from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DataSource
from app.schemas import DataSourceOut

router = APIRouter(prefix="/api/sources", tags=["data-fabric"])


@router.get("", response_model=list[DataSourceOut])
def list_sources(
    status_filter: str | None = Query(None, alias="status", description="connected | planned"),
    category: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Layer 1 - Data Fabric registry: every external/internal source the
    platform is designed to ingest from, and whether it's actually connected
    (a real agent calls it live) or still planned."""
    stmt = select(DataSource)
    if status_filter:
        stmt = stmt.where(DataSource.status == status_filter)
    if category:
        stmt = stmt.where(DataSource.category == category)
    return db.scalars(stmt.order_by(DataSource.status.desc(), DataSource.name)).all()
