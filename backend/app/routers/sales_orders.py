from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.document_services import sales_order_pdf_bytes, signed_document_payload, verify_document_payload
from app.models import (
    BillOfMaterialItem,
    Corporation,
    Delivery,
    DeliveryLine,
    DeliveryStatus,
    Department,
    FinishGoodReceipt,
    FinishGoodStatus,
    FulfillmentStatus,
    Product,
    SalesOrder,
    SalesOrderItem,
    SalesOrderMaterialAllocation,
    SalesOrderStatus,
    SalesOrderType,
    User,
    WipLotJob,
    WipLotStatus,
)
from app.module_permissions import (
    DepartmentModuleAccess,
    ensure_department_access,
    ensure_department_head,
    resolve_department_access,
)
from app.sales_order_services import (
    calculate_sales_line_amount,
    calculate_sales_total,
    ensure_sales_waiting_review,
    expand_bom_leaf_requirements,
    generate_sales_order_number,
)
from app.schemas import (
    PaginatedSalesOrders,
    SalesOrderCreate,
    SalesOrderItemResponse,
    SalesOrderRejection,
    SalesOrderResponse,
    SalesOrderUpdate,
)

router = APIRouter(prefix="/sales-orders", tags=["Sales Order"])


async def current_access(db: AsyncSession, user: User) -> DepartmentModuleAccess:
    department = await db.get(Department, settings.sales_department_code)
    access = resolve_department_access(user, department)
    ensure_department_access(access, "Sales")
    return access


async def get_order(db: AsyncSession, sales_order_number: str) -> SalesOrder:
    order = (
        await db.execute(
            select(SalesOrder)
            .options(selectinload(SalesOrder.items))
            .where(SalesOrder.sales_order_number == sales_order_number)
        )
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sales order not found")
    return order


async def order_response(db: AsyncSession, order: SalesOrder, access: DepartmentModuleAccess) -> SalesOrderResponse:
    creator = await db.get(User, order.created_by)
    reviewer = await db.get(User, order.reviewed_by) if order.reviewed_by else None
    waiting = order.status == SalesOrderStatus.waiting_review
    creator_name = f"{creator.first_name} {creator.last_name}".strip() if creator else order.created_by
    reviewer_name = f"{reviewer.first_name} {reviewer.last_name}".strip() if reviewer else None
    item_ids = [item.id for item in order.items]
    material_rows = list(
        (
            await db.execute(
                select(
                    SalesOrderMaterialAllocation.sales_order_item_id,
                    func.coalesce(func.sum(SalesOrderMaterialAllocation.received_quantity), 0),
                    func.coalesce(func.sum(SalesOrderMaterialAllocation.required_quantity), 0),
                )
                .where(SalesOrderMaterialAllocation.sales_order_item_id.in_(item_ids))
                .group_by(SalesOrderMaterialAllocation.sales_order_item_id)
            )
        ).all()
    )
    wip_rows = list(
        (
            await db.execute(
                select(WipLotJob.sales_order_item_id, func.coalesce(func.sum(WipLotJob.current_quantity), 0))
                .where(
                    WipLotJob.sales_order_item_id.in_(item_ids),
                    WipLotJob.status.not_in([WipLotStatus.completed, WipLotStatus.reversed]),
                )
                .group_by(WipLotJob.sales_order_item_id)
            )
        ).all()
    )
    finish_rows = list(
        (
            await db.execute(
                select(WipLotJob.sales_order_item_id, func.coalesce(func.sum(FinishGoodReceipt.quantity), 0))
                .join(FinishGoodReceipt, FinishGoodReceipt.source_wip_job_id == WipLotJob.id)
                .where(WipLotJob.sales_order_item_id.in_(item_ids), FinishGoodReceipt.status == FinishGoodStatus.posted)
                .group_by(WipLotJob.sales_order_item_id)
            )
        ).all()
    )
    dispatched_rows = list(
        (
            await db.execute(
                select(DeliveryLine.sales_order_item_id, func.coalesce(func.sum(DeliveryLine.quantity), 0))
                .join(Delivery, Delivery.delivery_number == DeliveryLine.delivery_number)
                .where(DeliveryLine.sales_order_item_id.in_(item_ids), Delivery.status == DeliveryStatus.dispatched)
                .group_by(DeliveryLine.sales_order_item_id)
            )
        ).all()
    )
    wip_by_item = {item_id: Decimal(str(quantity)) for item_id, quantity in wip_rows}
    material_by_item = {
        item_id: (Decimal(str(received)), Decimal(str(required))) for item_id, received, required in material_rows
    }
    finish_by_item = {item_id: Decimal(str(quantity)) for item_id, quantity in finish_rows}
    dispatched_by_item = {item_id: Decimal(str(quantity)) for item_id, quantity in dispatched_rows}
    item_responses = [
        SalesOrderItemResponse(
            id=item.id,
            line_number=item.line_number,
            product_code=item.product_code,
            part_name=item.part_name,
            part_no=item.part_no,
            description=item.description,
            quantity_grams=item.quantity_grams,
            unit=item.unit,
            material_received_quantity=material_by_item.get(
                item.id, (item.material_received_quantity, item.quantity_grams)
            )[0],
            outstanding_material_quantity=max(
                material_by_item.get(item.id, (item.material_received_quantity, item.quantity_grams))[1]
                - material_by_item.get(item.id, (item.material_received_quantity, item.quantity_grams))[0],
                Decimal("0"),
            ),
            delivered_quantity=item.delivered_quantity,
            outstanding_order_quantity=max(item.quantity_grams - item.delivered_quantity, Decimal("0")),
            outstanding_note=item.outstanding_note,
            unit_price=item.unit_price,
            amount=item.amount,
            remark=item.remark,
            wip_quantity=wip_by_item.get(item.id, Decimal("0")),
            finish_good_quantity=finish_by_item.get(item.id, Decimal("0")),
            dispatched_quantity=dispatched_by_item.get(item.id, Decimal("0")),
        )
        for item in order.items
    ]
    return SalesOrderResponse(
        sales_order_number=order.sales_order_number,
        po_receipt_date=order.po_receipt_date,
        customer_po_date=order.customer_po_date,
        customer_po_number=order.customer_po_number,
        customer_code=order.customer_code,
        customer_name=order.customer_name,
        bill_to_address=order.bill_to_address,
        bill_to_phone=order.bill_to_phone,
        ship_to_name=order.ship_to_name,
        ship_to_address=order.ship_to_address,
        ship_to_contact_person=order.ship_to_contact_person,
        ship_to_phone=order.ship_to_phone,
        delivery_date=order.delivery_date,
        order_type=order.order_type,
        notes=order.notes,
        currency=order.currency,
        subtotal=order.subtotal,
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
            "sales_order", order.sales_order_number, "created", order.created_by, creator_name, order.created_at
        ),
        approval_qr_payload=(
            signed_document_payload(
                "sales_order",
                order.sales_order_number,
                "approved",
                order.reviewed_by,
                reviewer_name or order.reviewed_by,
                order.reviewed_at,
            )
            if order.status == SalesOrderStatus.approved and order.reviewed_by and order.reviewed_at
            else None
        ),
        items=item_responses,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


async def apply_order_data(
    db: AsyncSession,
    order: SalesOrder,
    data: SalesOrderCreate | SalesOrderUpdate,
) -> None:
    customer = await db.get(Corporation, data.customer_code)
    if not customer or not customer.is_customer:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected corporation is not a customer",
        )

    new_items: list[SalesOrderItem] = []
    amounts: list[Decimal] = []
    for line_number, item_data in enumerate(data.items, start=1):
        product = await db.get(Product, item_data.product_code)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Product {item_data.product_code} does not exist",
            )
        if product.customer_code != customer.code:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Product {product.code} is not registered for customer {customer.code}",
            )
        amount = calculate_sales_line_amount(item_data.quantity_grams, item_data.unit_price)
        amounts.append(amount)
        new_items.append(
            SalesOrderItem(
                line_number=line_number,
                product_code=product.code,
                part_name=product.part_name,
                part_no=product.part_no,
                description=product.description,
                quantity_grams=item_data.quantity_grams,
                unit=item_data.unit.value,
                material_received_quantity=Decimal("0"),
                delivered_quantity=Decimal("0"),
                outstanding_note=item_data.outstanding_note,
                unit_price=item_data.unit_price,
                amount=amount,
                remark=item_data.remark,
            )
        )

    total = calculate_sales_total(amounts)
    order.po_receipt_date = data.po_receipt_date
    order.customer_po_date = data.customer_po_date
    order.customer_po_number = data.customer_po_number
    order.customer_code = customer.code
    order.customer_name = customer.name
    order.bill_to_address = customer.address
    order.bill_to_phone = customer.phone_number
    order.ship_to_name = data.ship_to_name or customer.name
    order.ship_to_address = data.ship_to_address or customer.address
    order.ship_to_contact_person = data.ship_to_contact_person or customer.contact_person_name
    order.ship_to_phone = data.ship_to_phone or customer.contact_person_phone
    order.delivery_date = data.delivery_date
    order.order_type = data.order_type
    order.notes = data.notes
    order.currency = "IDR"
    order.subtotal = total
    order.grand_total = total
    order.items = new_items
    db.add(order)
    await db.flush()
    bom_rows = list(
        (
            await db.execute(
                select(BillOfMaterialItem).where(BillOfMaterialItem.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    for item in new_items:
        try:
            requirements = expand_bom_leaf_requirements(item.product_code, item.quantity_grams, bom_rows)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        for material_product_code, required_quantity, unit in requirements:
            db.add(
                SalesOrderMaterialAllocation(
                    sales_order_item_id=item.id,
                    material_product_code=material_product_code,
                    required_quantity=required_quantity,
                    received_quantity=Decimal("0"),
                    unit=unit,
                )
            )


async def commit_order(db: AsyncSession, order: SalesOrder) -> None:
    try:
        await db.commit()
        await db.refresh(order)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sales order data conflicts with an existing record",
        ) from exc


@router.get("", response_model=PaginatedSalesOrders)
async def list_sales_orders(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: str | None = None,
    order_status: SalesOrderStatus | None = Query(default=None, alias="status"),
    order_type: SalesOrderType | None = None,
    fulfillment_status: FulfillmentStatus | None = None,
    outstanding_only: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedSalesOrders:
    access = await current_access(db, current_user)
    filters = [SalesOrder.department_code == settings.sales_department_code]
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                SalesOrder.sales_order_number.ilike(term),
                SalesOrder.customer_po_number.ilike(term),
                SalesOrder.customer_code.ilike(term),
                SalesOrder.customer_name.ilike(term),
            )
        )
    if order_status:
        filters.append(SalesOrder.status == order_status)
    if order_type:
        filters.append(SalesOrder.order_type == order_type)
    if fulfillment_status:
        filters.append(SalesOrder.fulfillment_status == fulfillment_status)
    if outstanding_only:
        filters.append(SalesOrder.fulfillment_status == FulfillmentStatus.open)
    if date_from:
        filters.append(SalesOrder.po_receipt_date >= date_from)
    if date_to:
        filters.append(SalesOrder.po_receipt_date <= date_to)
    query = (
        select(SalesOrder)
        .options(selectinload(SalesOrder.items))
        .where(*filters)
        .order_by(SalesOrder.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    orders = list((await db.execute(query)).scalars().all())
    total = (await db.execute(select(func.count()).select_from(SalesOrder).where(*filters))).scalar_one()
    summary_orders = list(
        (await db.execute(select(SalesOrder).options(selectinload(SalesOrder.items)).where(*filters))).scalars().all()
    )
    total_material: dict[str, Decimal] = {}
    outstanding_material: dict[str, Decimal] = {}
    for summary_order in summary_orders:
        for item in summary_order.items:
            total_material[item.unit] = total_material.get(item.unit, Decimal("0")) + item.quantity_grams
            outstanding_material[item.unit] = outstanding_material.get(item.unit, Decimal("0")) + max(
                item.quantity_grams - item.material_received_quantity, Decimal("0")
            )
    return PaginatedSalesOrders(
        items=[await order_response(db, order, access) for order in orders],
        total=total,
        page=page,
        size=size,
        total_order=total,
        outstanding_order=sum(order.fulfillment_status == FulfillmentStatus.open for order in summary_orders),
        total_material_by_unit=total_material,
        outstanding_material_by_unit=outstanding_material,
    )


@router.post("", response_model=SalesOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_sales_order(
    data: SalesOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SalesOrderResponse:
    access = await current_access(db, current_user)
    order = SalesOrder(
        sales_order_number=await generate_sales_order_number(db, data.po_receipt_date),
        status=SalesOrderStatus.waiting_review,
        fulfillment_status=FulfillmentStatus.open,
        department_code=settings.sales_department_code,
        created_by=current_user.id,
    )
    await apply_order_data(db, order, data)
    await commit_order(db, order)
    return await order_response(db, await get_order(db, order.sales_order_number), access)


@router.get("/{sales_order_number}", response_model=SalesOrderResponse)
async def get_sales_order(
    sales_order_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SalesOrderResponse:
    access = await current_access(db, current_user)
    return await order_response(db, await get_order(db, sales_order_number), access)


@router.get("/{sales_order_number}/pdf")
async def download_sales_order_pdf(
    sales_order_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    access = await current_access(db, current_user)
    order = await get_order(db, sales_order_number)
    content = sales_order_pdf_bytes(await order_response(db, order, access))
    safe_number = order.sales_order_number.replace("/", "-")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="sales-order-{safe_number}.pdf"'},
    )


@router.patch("/{sales_order_number}", response_model=SalesOrderResponse)
async def update_sales_order(
    sales_order_number: str,
    data: SalesOrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SalesOrderResponse:
    access = await current_access(db, current_user)
    order = await get_order(db, sales_order_number)
    ensure_sales_waiting_review(order.status)
    order.items.clear()
    await db.flush()
    await apply_order_data(db, order, data)
    await commit_order(db, order)
    return await order_response(db, await get_order(db, sales_order_number), access)


@router.delete("/{sales_order_number}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sales_order(
    sales_order_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    await current_access(db, current_user)
    order = await get_order(db, sales_order_number)
    ensure_sales_waiting_review(order.status)
    await db.delete(order)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{sales_order_number}/approve", response_model=SalesOrderResponse)
async def approve_sales_order(
    sales_order_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SalesOrderResponse:
    access = await current_access(db, current_user)
    ensure_department_head(access, "Sales")
    order = await get_order(db, sales_order_number)
    ensure_sales_waiting_review(order.status)
    order.status = SalesOrderStatus.approved
    order.reviewed_by = current_user.id
    order.reviewed_at = datetime.now(timezone.utc)
    order.rejection_reason = None
    await commit_order(db, order)
    return await order_response(db, order, access)


@router.post("/{sales_order_number}/reject", response_model=SalesOrderResponse)
async def reject_sales_order(
    sales_order_number: str,
    data: SalesOrderRejection,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SalesOrderResponse:
    access = await current_access(db, current_user)
    ensure_department_head(access, "Sales")
    order = await get_order(db, sales_order_number)
    ensure_sales_waiting_review(order.status)
    order.status = SalesOrderStatus.rejected
    order.fulfillment_status = FulfillmentStatus.closed
    order.reviewed_by = current_user.id
    order.reviewed_at = datetime.now(timezone.utc)
    order.rejection_reason = data.reason
    await commit_order(db, order)
    return await order_response(db, order, access)


@router.get("/verification/qr/{token}")
async def verify_sales_order_qr(token: str, current_user: User = Depends(get_current_user)) -> dict[str, object]:
    del current_user
    try:
        return {"valid": True, **verify_document_payload(token)}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid QR payload") from exc
