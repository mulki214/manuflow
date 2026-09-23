from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.document_services import purchase_request_pdf_bytes, signed_document_payload
from app.models import (
    AccessLevel, DailyPurchaseRequestSequence, Product, PurchaseRequest,
    PurchaseRequestItem, PurchaseRequestStatus, User,
)
from app.schemas import (
    PaginatedPurchaseRequests, PurchaseRequestCreate, PurchaseRequestRejection,
    PurchaseRequestResponse,
)

router = APIRouter(prefix="/purchase-requests", tags=["Purchase Requests"])


def can_review(user: User) -> bool:
    return user.access_level == AccessLevel.administrator or (
        user.access_level == AccessLevel.head
        and user.department_code == settings.purchasing_department_code
    )


async def get_request(db: AsyncSession, number: str) -> PurchaseRequest:
    record = (await db.execute(select(PurchaseRequest).options(selectinload(PurchaseRequest.items)).where(PurchaseRequest.request_number == number))).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Purchase Request not found")
    return record


async def response(db: AsyncSession, record: PurchaseRequest, user: User) -> PurchaseRequestResponse:
    creator = await db.get(User, record.created_by)
    reviewer = await db.get(User, record.reviewed_by) if record.reviewed_by else None
    creator_name = f"{creator.first_name} {creator.last_name}".strip() if creator else record.created_by
    reviewer_name = f"{reviewer.first_name} {reviewer.last_name}".strip() if reviewer else None
    return PurchaseRequestResponse(
        request_number=record.request_number, request_date=record.request_date,
        department_code=record.department_code, notes=record.notes, status=record.status,
        created_by=record.created_by, created_by_name=creator_name,
        reviewed_by=record.reviewed_by, reviewed_by_name=reviewer_name,
        reviewed_at=record.reviewed_at, rejection_reason=record.rejection_reason,
        can_review=record.status == PurchaseRequestStatus.waiting_review and can_review(user),
        creator_qr_payload=signed_document_payload("purchase_request", record.request_number, "submitted", record.created_by, creator_name, record.created_at),
        review_qr_payload=(signed_document_payload("purchase_request", record.request_number, record.status.value, record.reviewed_by, reviewer_name or record.reviewed_by, record.reviewed_at) if record.status != PurchaseRequestStatus.waiting_review and record.reviewed_by and record.reviewed_at else None),
        items=record.items, created_at=record.created_at, updated_at=record.updated_at,
    )


async def next_number(db: AsyncSession, request_date) -> str:
    value = (await db.execute(insert(DailyPurchaseRequestSequence).values(sequence_date=request_date, last_value=0).on_conflict_do_update(index_elements=[DailyPurchaseRequestSequence.sequence_date], set_={"last_value": DailyPurchaseRequestSequence.last_value + 1}).returning(DailyPurchaseRequestSequence.last_value))).scalar_one()
    if value > 999:
        raise HTTPException(status_code=409, detail="The daily Purchase Request limit of 999 has been reached")
    return f"PR-{request_date:%d%m%y}-{value:03d}"


def assert_visible(record: PurchaseRequest, user: User) -> None:
    if not can_review(user) and record.created_by != user.id:
        raise HTTPException(status_code=403, detail="You can only access your own Purchase Requests")


@router.get("", response_model=PaginatedPurchaseRequests)
async def list_requests(page: int = Query(1, ge=1), size: int = Query(10, ge=1, le=100), search: str | None = None, request_status: PurchaseRequestStatus | None = Query(None, alias="status"), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> PaginatedPurchaseRequests:
    filters = []
    if not can_review(current_user): filters.append(PurchaseRequest.created_by == current_user.id)
    if search: filters.append(or_(PurchaseRequest.request_number.ilike(f"%{search.strip()}%"), PurchaseRequest.created_by.ilike(f"%{search.strip()}%")))
    if request_status: filters.append(PurchaseRequest.status == request_status)
    records = list((await db.execute(select(PurchaseRequest).options(selectinload(PurchaseRequest.items)).where(*filters).order_by(PurchaseRequest.created_at.desc()).offset((page - 1) * size).limit(size))).scalars())
    total = await db.scalar(select(func.count()).select_from(PurchaseRequest).where(*filters))
    return PaginatedPurchaseRequests(items=[await response(db, record, current_user) for record in records], total=total or 0, page=page, size=size)


@router.post("", response_model=PurchaseRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(data: PurchaseRequestCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> PurchaseRequestResponse:
    record = PurchaseRequest(request_number=await next_number(db, data.request_date), request_date=data.request_date, department_code=current_user.department_code, notes=data.notes.strip(), created_by=current_user.id)
    for index, item in enumerate(data.items, 1):
        product = await db.get(Product, item.product_code)
        if not product or not product.is_active: raise HTTPException(status_code=422, detail=f"Product {item.product_code} is not active")
        if product.unit != item.unit.value: raise HTTPException(status_code=422, detail=f"Unit must match product {product.code}")
        record.items.append(PurchaseRequestItem(line_number=index, product_code=product.code, part_name=product.part_name, part_no=product.part_no, description=product.description, quantity=item.quantity, unit=item.unit.value, remark=item.remark.strip()))
    db.add(record); await db.commit(); return await response(db, await get_request(db, record.request_number), current_user)


@router.get("/{request_number}", response_model=PurchaseRequestResponse)
async def get_one(request_number: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> PurchaseRequestResponse:
    record = await get_request(db, request_number); assert_visible(record, current_user); return await response(db, record, current_user)


@router.get("/{request_number}/pdf")
async def download_pdf(request_number: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    record = await get_request(db, request_number)
    assert_visible(record, current_user)
    payload = await response(db, record, current_user)
    content = purchase_request_pdf_bytes(payload)
    return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="purchase-request-{record.request_number}.pdf"'})


@router.post("/{request_number}/approve", response_model=PurchaseRequestResponse)
async def approve(request_number: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> PurchaseRequestResponse:
    if not can_review(current_user): raise HTTPException(status_code=403, detail="Only Head Purchasing can review Purchase Requests")
    record = await get_request(db, request_number)
    if record.status != PurchaseRequestStatus.waiting_review: raise HTTPException(status_code=409, detail="Purchase Request has already been reviewed")
    record.status = PurchaseRequestStatus.approved; record.reviewed_by = current_user.id; record.reviewed_at = datetime.now(ZoneInfo(settings.business_timezone)); await db.commit(); return await response(db, await get_request(db, request_number), current_user)


@router.post("/{request_number}/reject", response_model=PurchaseRequestResponse)
async def reject(request_number: str, data: PurchaseRequestRejection, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> PurchaseRequestResponse:
    if not can_review(current_user): raise HTTPException(status_code=403, detail="Only Head Purchasing can review Purchase Requests")
    record = await get_request(db, request_number)
    if record.status != PurchaseRequestStatus.waiting_review: raise HTTPException(status_code=409, detail="Purchase Request has already been reviewed")
    record.status = PurchaseRequestStatus.rejected; record.reviewed_by = current_user.id; record.reviewed_at = datetime.now(ZoneInfo(settings.business_timezone)); record.rejection_reason = data.reason.strip(); await db.commit(); return await response(db, await get_request(db, request_number), current_user)
