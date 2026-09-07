from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.document_services import purchase_order_pdf_bytes, signed_document_payload, verify_document_payload
from app.models import (
    Corporation,
    Department,
    FulfillmentStatus,
    Plant,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    User,
)
from app.purchasing_permissions import (
    PurchasingAccess,
    ensure_purchasing_access,
    ensure_purchasing_head,
    resolve_purchasing_access,
)
from app.purchasing_services import (
    calculate_line_amount,
    calculate_purchase_totals,
    ensure_waiting_review,
    generate_purchase_order_number,
    payment_due_date,
)
from app.schemas import (
    PaginatedPurchaseOrders,
    PurchaseOrderCreate,
    PurchaseOrderItemResponse,
    PurchaseOrderRejection,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
)

router = APIRouter(prefix="/purchasing", tags=["Purchasing"])


async def current_access(db: AsyncSession, user: User) -> PurchasingAccess:
    department = await db.get(Department, settings.purchasing_department_code)
    access = resolve_purchasing_access(user, department)
    ensure_purchasing_access(access)
    return access


async def get_order(db: AsyncSession, po_number: str) -> PurchaseOrder:
    order = (
        await db.execute(
            select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(PurchaseOrder.po_number == po_number)
        )
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    return order


async def order_response(db: AsyncSession, order: PurchaseOrder, access: PurchasingAccess) -> PurchaseOrderResponse:
    creator = await db.get(User, order.created_by)
    reviewer = await db.get(User, order.reviewed_by) if order.reviewed_by else None
    waiting = order.status == PurchaseOrderStatus.waiting_review
    creator_name = f"{creator.first_name} {creator.last_name}".strip() if creator else order.created_by
    reviewer_name = f"{reviewer.first_name} {reviewer.last_name}".strip() if reviewer else None
    item_responses = [
        PurchaseOrderItemResponse(
            id=item.id,
            line_number=item.line_number,
            product_code=item.product_code,
            part_name=item.part_name,
            part_no=item.part_no,
            description=item.description,
            quantity_grams=item.quantity_grams,
            unit=item.unit,
            received_quantity=item.received_quantity,
            outstanding_quantity=max(item.quantity_grams - item.received_quantity, Decimal("0")),
            unit_price=item.unit_price,
            amount=item.amount,
            remark=item.remark,
        )
        for item in order.items
    ]
    return PurchaseOrderResponse(
        po_number=order.po_number,
        po_date=order.po_date,
        supplier_code=order.supplier_code,
        supplier_name=order.supplier_name,
        supplier_address=order.supplier_address,
        supplier_phone=order.supplier_phone,
        supplier_contact_person=order.supplier_contact_person,
        quotation_reference=order.quotation_reference,
        quotation_date=order.quotation_date,
        requested_delivery_date=order.requested_delivery_date,
        delivery_plant_code=order.delivery_plant_code,
        delivery_plant_name=order.delivery_plant_name,
        delivery_address=order.delivery_address,
        notes=order.notes,
        payment_terms_days=order.payment_terms_days,
        payment_due_date=order.payment_due_date,
        currency=order.currency,
        subtotal=order.subtotal,
        discount_amount=order.discount_amount,
        ppn_rate=order.ppn_rate,
        ppn_amount=order.ppn_amount,
        pph23_rate=order.pph23_rate,
        pph23_amount=order.pph23_amount,
        grand_total=order.grand_total,
        status=order.status,
        fulfillment_status=order.fulfillment_status,
        department_code=order.department_code,
        created_by=order.created_by,
        created_by_name=creator_name,
        reviewed_by=order.reviewed_by,
        reviewed_by_name=reviewer_name,
        reviewed_at=order.reviewed_at,
        rejection_reason=order.rejection_reason,
        can_edit=waiting,
        can_delete=waiting,
        can_review=waiting and access.can_review,
        creator_qr_payload=signed_document_payload(
            "purchase_order", order.po_number, "created", order.created_by, creator_name, order.created_at
        ),
        approval_qr_payload=(
            signed_document_payload(
                "purchase_order",
                order.po_number,
                "approved",
                order.reviewed_by,
                reviewer_name or order.reviewed_by,
                order.reviewed_at,
            )
            if order.status == PurchaseOrderStatus.approved and order.reviewed_by and order.reviewed_at
            else None
        ),
        items=item_responses,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


async def apply_order_data(
    db: AsyncSession,
    order: PurchaseOrder,
    data: PurchaseOrderCreate | PurchaseOrderUpdate,
) -> None:
    supplier = await db.get(Corporation, data.supplier_code)
    if not supplier or not supplier.is_supplier:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected corporation is not a supplier",
        )
    plant = await db.get(Plant, data.delivery_plant_code)
    if not plant:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected plant does not exist",
        )

    new_items: list[PurchaseOrderItem] = []
    amounts: list[Decimal] = []
    for line_number, item_data in enumerate(data.items, start=1):
        product = await db.get(Product, item_data.product_code)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Product {item_data.product_code} does not exist",
            )
        if product.supplier_code != supplier.code:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Product {product.code} is not registered for supplier {supplier.code}",
            )
        amount = calculate_line_amount(item_data.quantity_grams, item_data.unit_price)
        amounts.append(amount)
        new_items.append(
            PurchaseOrderItem(
                line_number=line_number,
                product_code=product.code,
                part_name=product.part_name,
                part_no=product.part_no,
                description=product.description,
                quantity_grams=item_data.quantity_grams,
                unit=item_data.unit.value,
                received_quantity=Decimal("0"),
                unit_price=item_data.unit_price,
                amount=amount,
                remark=item_data.remark,
            )
        )

    try:
        totals = calculate_purchase_totals(amounts, data.discount_amount, data.ppn_rate, data.pph23_rate)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    order.po_date = data.po_date
    order.supplier_code = supplier.code
    order.supplier_name = supplier.name
    order.supplier_address = supplier.address
    order.supplier_phone = supplier.phone_number
    order.supplier_contact_person = supplier.contact_person_name
    order.quotation_reference = data.quotation_reference
    order.quotation_date = data.quotation_date
    order.requested_delivery_date = data.requested_delivery_date
    order.delivery_plant_code = plant.code
    order.delivery_plant_name = plant.name
    order.delivery_address = plant.full_address
    order.notes = data.notes
    order.payment_terms_days = data.payment_terms_days
    order.payment_due_date = payment_due_date(data.po_date, data.payment_terms_days)
    order.currency = "IDR"
    order.subtotal = totals.subtotal
    order.discount_amount = totals.discount_amount
    order.ppn_rate = data.ppn_rate
    order.ppn_amount = totals.ppn_amount
    order.pph23_rate = data.pph23_rate
    order.pph23_amount = totals.pph23_amount
    order.grand_total = totals.grand_total
    order.items = new_items


async def commit_order(db: AsyncSession, order: PurchaseOrder) -> None:
    try:
        await db.commit()
        await db.refresh(order)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Purchase order data conflicts with an existing record",
        ) from exc


@router.get("", response_model=PaginatedPurchaseOrders)
async def list_purchase_orders(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    order_status: PurchaseOrderStatus | None = Query(default=None, alias="status"),
    fulfillment_status: FulfillmentStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedPurchaseOrders:
    access = await current_access(db, current_user)
    filters = [PurchaseOrder.department_code == settings.purchasing_department_code]
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                PurchaseOrder.po_number.ilike(term),
                PurchaseOrder.supplier_code.ilike(term),
                PurchaseOrder.supplier_name.ilike(term),
            )
        )
    if order_status:
        filters.append(PurchaseOrder.status == order_status)
    if fulfillment_status:
        filters.append(PurchaseOrder.fulfillment_status == fulfillment_status)
    if date_from:
        filters.append(PurchaseOrder.po_date >= date_from)
    if date_to:
        filters.append(PurchaseOrder.po_date <= date_to)
    query = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(*filters)
        .order_by(PurchaseOrder.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    orders = list((await db.execute(query)).scalars().all())
    total = (await db.execute(select(func.count()).select_from(PurchaseOrder).where(*filters))).scalar_one()
    return PaginatedPurchaseOrders(
        items=[await order_response(db, order, access) for order in orders],
        total=total,
        page=page,
        size=size,
    )


@router.post("", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PurchaseOrderResponse:
    access = await current_access(db, current_user)
    order = PurchaseOrder(
        po_number=await generate_purchase_order_number(db, data.po_date),
        status=PurchaseOrderStatus.waiting_review,
        fulfillment_status=FulfillmentStatus.open,
        department_code=settings.purchasing_department_code,
        created_by=current_user.id,
    )
    await apply_order_data(db, order, data)
    db.add(order)
    await commit_order(db, order)
    order = await get_order(db, order.po_number)
    return await order_response(db, order, access)


@router.get("/{po_number}", response_model=PurchaseOrderResponse)
async def get_purchase_order(
    po_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PurchaseOrderResponse:
    access = await current_access(db, current_user)
    return await order_response(db, await get_order(db, po_number), access)


@router.get("/{po_number}/pdf")
async def download_purchase_order_pdf(
    po_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    access = await current_access(db, current_user)
    response = await order_response(db, await get_order(db, po_number), access)
    content = purchase_order_pdf_bytes(response)
    safe_number = po_number.replace("/", "-")
    return StreamingResponse(
        iter([content]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="purchase-order-{safe_number}.pdf"'},
    )


@router.patch("/{po_number}", response_model=PurchaseOrderResponse)
async def update_purchase_order(
    po_number: str,
    data: PurchaseOrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PurchaseOrderResponse:
    access = await current_access(db, current_user)
    order = await get_order(db, po_number)
    ensure_waiting_review(order.status)
    order.items.clear()
    await db.flush()
    await apply_order_data(db, order, data)
    await commit_order(db, order)
    return await order_response(db, await get_order(db, po_number), access)


@router.delete("/{po_number}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase_order(
    po_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    await current_access(db, current_user)
    order = await get_order(db, po_number)
    ensure_waiting_review(order.status)
    await db.delete(order)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{po_number}/approve", response_model=PurchaseOrderResponse)
async def approve_purchase_order(
    po_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PurchaseOrderResponse:
    access = await current_access(db, current_user)
    ensure_purchasing_head(access)
    order = await get_order(db, po_number)
    ensure_waiting_review(order.status)
    order.status = PurchaseOrderStatus.approved
    order.reviewed_by = current_user.id
    order.reviewed_at = datetime.now(timezone.utc)
    order.rejection_reason = None
    await commit_order(db, order)
    return await order_response(db, order, access)


@router.post("/{po_number}/reject", response_model=PurchaseOrderResponse)
async def reject_purchase_order(
    po_number: str,
    data: PurchaseOrderRejection,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PurchaseOrderResponse:
    access = await current_access(db, current_user)
    ensure_purchasing_head(access)
    order = await get_order(db, po_number)
    ensure_waiting_review(order.status)
    order.status = PurchaseOrderStatus.rejected
    order.fulfillment_status = FulfillmentStatus.closed
    order.reviewed_by = current_user.id
    order.reviewed_at = datetime.now(timezone.utc)
    order.rejection_reason = data.reason
    await commit_order(db, order)
    return await order_response(db, order, access)


@router.get("/verification/qr/{token}")
async def verify_purchase_order_qr(token: str, current_user: User = Depends(get_current_user)) -> dict[str, object]:
    del current_user
    try:
        return {"valid": True, **verify_document_payload(token)}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR payload") from exc
