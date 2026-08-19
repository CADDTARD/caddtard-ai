from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChecklistItem
from app.schemas import ChecklistItemOut, ChecklistToggleIn

router = APIRouter(prefix="/api/checklist", tags=["checklist"])


@router.get("", response_model=list[ChecklistItemOut])
def list_checklist(
    candidate: str = Query("global", description="Candidate slug, or 'global' for the shared checklist"),
    db: Session = Depends(get_db),
):
    """IND-readiness checklist state, persisted server-side (replaces the browser
    localStorage used in the prototype dashboard) so progress survives across
    machines and browsers."""
    stmt = select(ChecklistItem).where(ChecklistItem.candidate_slug == candidate).order_by(ChecklistItem.sort_order)
    return db.scalars(stmt).all()


@router.patch("/{item_id}", response_model=ChecklistItemOut)
def toggle_checklist_item(item_id: int, body: ChecklistToggleIn, db: Session = Depends(get_db)):
    item = db.get(ChecklistItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Checklist item {item_id} not found")
    item.checked = body.checked
    db.commit()
    db.refresh(item)
    return item
