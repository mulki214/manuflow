from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import AccessLevel, QrLabel, User
from app.schemas import PaginatedQrLabels, QrLabelCreate, QrLabelResponse, QrLabelUpdate

router = APIRouter(prefix="/qr-labels", tags=["QR Labels"])


def response(record: QrLabel) -> QrLabelResponse:
    return QrLabelResponse.model_validate(record, from_attributes=True)


def can_manage(record: QrLabel, user: User) -> bool:
    return record.created_by == user.id or user.access_level == AccessLevel.administrator


@router.get("", response_model=PaginatedQrLabels)
async def list_qr_labels(
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), search: str | None = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
) -> PaginatedQrLabels:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(QrLabel.label_name.ilike(term), QrLabel.resolved_text.ilike(term), QrLabel.created_by_name.ilike(term)))
    query = select(QrLabel).where(*filters).order_by(QrLabel.created_at.desc(), QrLabel.id.desc())
    records = list((await db.execute(query.offset((page - 1) * size).limit(size))).scalars())
    total = await db.scalar(select(func.count()).select_from(QrLabel).where(*filters))
    return PaginatedQrLabels(items=[response(item) for item in records], total=total or 0, page=page, size=size)


@router.post("", response_model=QrLabelResponse, status_code=status.HTTP_201_CREATED)
async def create_qr_label(data: QrLabelCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> QrLabelResponse:
    record = QrLabel(**data.model_dump(), created_by=current_user.id, created_by_name=f"{current_user.first_name} {current_user.last_name}".strip())
    db.add(record); await db.commit(); await db.refresh(record)
    return response(record)


async def get_record(label_id: int, db: AsyncSession) -> QrLabel:
    record = await db.get(QrLabel, label_id)
    if not record: raise HTTPException(status_code=404, detail="QR Label not found")
    return record


@router.patch("/{label_id}", response_model=QrLabelResponse)
async def update_qr_label(label_id: int, data: QrLabelUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> QrLabelResponse:
    record = await get_record(label_id, db)
    if not can_manage(record, current_user): raise HTTPException(status_code=403, detail="Only the creator or an administrator can edit this QR Label")
    for key, value in data.model_dump().items(): setattr(record, key, value)
    await db.commit(); await db.refresh(record); return response(record)


@router.delete("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_qr_label(label_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    record = await get_record(label_id, db)
    if not can_manage(record, current_user): raise HTTPException(status_code=403, detail="Only the creator or an administrator can delete this QR Label")
    await db.delete(record); await db.commit()
