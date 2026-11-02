from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.document_services import invoice_pdf_bytes
from app.invoice_services import (
    generate_invoice_number,
    invoice_line_amount,
    invoice_quantity_available,
    invoice_totals,
)
from app.models import (
    Corporation,
    Delivery,
    DeliveryLine,
    DeliveryStatus,
    Department,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    SalesOrder,
    SalesOrderItem,
    User,
)
from app.module_permissions import DepartmentModuleAccess, ensure_department_access, resolve_department_access
from app.operational_services import require_whole_quantity
from app.schemas import (
    InvoiceCreate,
    InvoiceItemResponse,
    InvoiceResponse,
    InvoiceVoidRequest,
    PaginatedInvoices,
)

router = APIRouter(prefix="/invoices", tags=["Invoice"])


async def current_access(db: AsyncSession, user: User) -> DepartmentModuleAccess:
    department = await db.get(Department, settings.sales_department_code)
    access = resolve_department_access(user, department)
    ensure_department_access(access, "Sales")
    return access


async def get_invoice(db: AsyncSession, number: str, *, lock: bool = False) -> Invoice:
    statement = select(Invoice).options(selectinload(Invoice.items)).where(Invoice.invoice_number == number)
    if lock:
        statement = statement.with_for_update()
    invoice = (await db.execute(statement)).scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


async def source_lines(db: AsyncSession, delivery: Delivery) -> list[SimpleNamespace]:
    lines = list(
        (
            await db.execute(
                select(DeliveryLine)
                .where(DeliveryLine.delivery_number == delivery.delivery_number)
                .order_by(DeliveryLine.id)
            )
        )
        .scalars()
        .all()
    )
    if lines:
        return [
            SimpleNamespace(
                id=line.id,
                sales_order_item_id=line.sales_order_item_id,
                product_code=line.product_code,
                lot_number=line.lot_number,
                quantity=line.quantity,
                unit=line.unit,
            )
            for line in lines
        ]
    # Older deliveries stored one line on the header and have no detail rows.
    return [
        SimpleNamespace(
            id=None,
            sales_order_item_id=delivery.sales_order_item_id,
            product_code=delivery.product_code,
            lot_number=delivery.lot_number,
            quantity=delivery.quantity,
            unit=delivery.unit,
        )
    ]


async def billed_quantity(
    db: AsyncSession,
    delivery_number: str,
    delivery_line_id: int | None,
    sales_order_item_id: int,
) -> Decimal:
    statement = (
        select(func.coalesce(func.sum(InvoiceItem.quantity), 0))
        .join(Invoice, Invoice.invoice_number == InvoiceItem.invoice_number)
        .where(
            InvoiceItem.delivery_number == delivery_number,
            InvoiceItem.sales_order_item_id == sales_order_item_id,
            Invoice.status == InvoiceStatus.issued,
        )
    )
    if delivery_line_id is None:
        statement = statement.where(InvoiceItem.delivery_line_id.is_(None))
    else:
        statement = statement.where(InvoiceItem.delivery_line_id == delivery_line_id)
    value = await db.scalar(statement)
    return Decimal(str(value or 0))


async def eligible_lines_for_delivery(db: AsyncSession, delivery: Delivery) -> list[dict]:
    if delivery.status not in {DeliveryStatus.delivered, DeliveryStatus.posted}:
        return []
    order = await db.get(SalesOrder, delivery.sales_order_number)
    if order is None:
        return []
    result: list[dict] = []
    for line in await source_lines(db, delivery):
        item = await db.get(SalesOrderItem, line.sales_order_item_id)
        if item is None:
            continue
        already_billed = await billed_quantity(db, delivery.delivery_number, line.id, item.id)
        available = invoice_quantity_available(line.quantity, already_billed)
        if available <= 0:
            continue
        result.append(
            {
                "delivery_number": delivery.delivery_number,
                "delivery_date": delivery.delivery_date,
                "delivery_line_id": line.id,
                "sales_order_number": order.sales_order_number,
                "sales_order_item_id": item.id,
                "customer_code": order.customer_code,
                "customer_name": order.customer_name,
                "product_code": item.product_code,
                "part_name": item.part_name,
                "part_no": item.part_no,
                "description": item.description,
                "lot_number": line.lot_number,
                "delivered_quantity": line.quantity,
                "invoiced_quantity": already_billed,
                "available_quantity": available,
                "unit": line.unit,
                "unit_price": item.unit_price,
                "available_amount": invoice_line_amount(available, item.unit_price),
            }
        )
    return result


def invoice_response(invoice: Invoice) -> InvoiceResponse:
    return InvoiceResponse(
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        sales_order_number=invoice.sales_order_number,
        customer_code=invoice.customer_code,
        customer_name=invoice.customer_name,
        customer_address=invoice.customer_address,
        customer_phone=invoice.customer_phone,
        customer_contact_person=invoice.customer_contact_person,
        notes=invoice.notes,
        payment_terms=invoice.payment_terms,
        currency=invoice.currency,
        subtotal=invoice.subtotal,
        discount_amount=invoice.discount_amount,
        tax_label=invoice.tax_label,
        tax_rate=invoice.tax_rate,
        tax_amount=invoice.tax_amount,
        grand_total=invoice.grand_total,
        status=invoice.status,
        created_by=invoice.created_by,
        created_by_name=invoice.created_by_name,
        voided_by_name=invoice.voided_by_name,
        voided_at=invoice.voided_at,
        void_reason=invoice.void_reason,
        items=[InvoiceItemResponse.model_validate(item) for item in invoice.items],
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


@router.get("/eligible-deliveries")
async def list_eligible_deliveries(
    sales_order_number: str = Query(min_length=1, max_length=20),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=200),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await current_access(db, current_user)
    filters = [
        Delivery.status.in_([DeliveryStatus.delivered, DeliveryStatus.posted]),
        Delivery.sales_order_number == sales_order_number,
    ]
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Delivery.delivery_number.ilike(term),
                Delivery.sales_order_number.ilike(term),
                Delivery.customer_name.ilike(term),
                Delivery.lot_number.ilike(term),
            )
        )
    records = list(
        (
            await db.execute(
                select(Delivery)
                .where(*filters)
                .order_by(Delivery.delivery_date.desc(), Delivery.delivery_number.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .scalars()
        .all()
    )
    total = await db.scalar(select(func.count()).select_from(Delivery).where(*filters)) or 0
    rows = []
    for delivery in records:
        lines = await eligible_lines_for_delivery(db, delivery)
        rows.extend(lines)
    return {"items": rows, "total_deliveries": total, "page": page, "size": size}


@router.get("/eligible-sales-orders")
async def list_invoice_eligible_sales_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    await current_access(db, current_user)
    deliveries = list(
        (
            await db.execute(
                select(Delivery)
                .where(Delivery.status.in_([DeliveryStatus.delivered, DeliveryStatus.posted]))
                .order_by(Delivery.delivery_date.desc(), Delivery.delivery_number.desc())
            )
        )
        .scalars()
        .all()
    )
    orders: dict[str, dict] = {}
    for delivery in deliveries:
        lines = await eligible_lines_for_delivery(db, delivery)
        if not lines:
            continue
        order = orders.setdefault(
            delivery.sales_order_number,
            {
                "sales_order_number": delivery.sales_order_number,
                "customer_code": lines[0]["customer_code"],
                "customer_name": lines[0]["customer_name"],
                "delivery_count": 0,
                "item_count": 0,
                "_deliveries": set(),
            },
        )
        order["_deliveries"].add(delivery.delivery_number)
        order["item_count"] += len(lines)
    result = []
    for order in orders.values():
        order["delivery_count"] = len(order.pop("_deliveries"))
        result.append(order)
    return result


@router.get("", response_model=PaginatedInvoices)
async def list_invoices(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedInvoices:
    await current_access(db, current_user)
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Invoice.invoice_number.ilike(term),
                Invoice.customer_name.ilike(term),
                Invoice.customer_code.ilike(term),
                Invoice.sales_order_number.ilike(term),
                Invoice.items.any(InvoiceItem.delivery_number.ilike(term)),
            )
        )
    if from_date:
        filters.append(Invoice.invoice_date >= from_date)
    if to_date:
        filters.append(Invoice.invoice_date <= to_date)
    total = await db.scalar(select(func.count()).select_from(Invoice).where(*filters)) or 0
    invoices = list(
        (
            await db.execute(
                select(Invoice)
                .options(selectinload(Invoice.items))
                .where(*filters)
                .order_by(Invoice.invoice_date.desc(), Invoice.invoice_number.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        .scalars()
        .all()
    )
    return PaginatedInvoices(
        items=[invoice_response(invoice) for invoice in invoices], total=total, page=page, size=size
    )


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    data: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceResponse:
    await current_access(db, current_user)
    delivery_numbers = sorted({line.delivery_number for line in data.items})
    deliveries = list(
        (
            await db.execute(
                select(Delivery)
                .where(Delivery.delivery_number.in_(delivery_numbers))
                .order_by(Delivery.delivery_number)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    delivery_by_number = {delivery.delivery_number: delivery for delivery in deliveries}
    if len(delivery_by_number) != len(delivery_numbers):
        raise HTTPException(status_code=422, detail="One or more selected deliveries do not exist")

    requested_items: list[InvoiceItem] = []
    amounts: list[Decimal] = []
    customer_codes: set[str] = set()
    orders: dict[str, SalesOrder] = {}
    for line_number, line_data in enumerate(data.items, start=1):
        delivery = delivery_by_number[line_data.delivery_number]
        if delivery.sales_order_number != data.sales_order_number:
            raise HTTPException(
                status_code=422,
                detail="Every selected delivery must belong to the selected Sales Order",
            )
        if delivery.status not in {DeliveryStatus.delivered, DeliveryStatus.posted}:
            raise HTTPException(status_code=409, detail=f"Delivery {delivery.delivery_number} is not delivered")
        order = orders.get(delivery.sales_order_number)
        if order is None:
            order = await db.get(SalesOrder, delivery.sales_order_number)
            if order is None:
                raise HTTPException(status_code=422, detail=f"Sales Order for {delivery.delivery_number} was not found")
            orders[order.sales_order_number] = order
        customer_codes.add(order.customer_code)
        source = next(
            (
                item
                for item in await source_lines(db, delivery)
                if item.id == line_data.delivery_line_id and item.sales_order_item_id == line_data.sales_order_item_id
            ),
            None,
        )
        if line_data.delivery_line_id is None:
            legacy_sources = await source_lines(db, delivery)
            source = next(
                (
                    item
                    for item in legacy_sources
                    if item.id is None and item.sales_order_item_id == line_data.sales_order_item_id
                ),
                None,
            )
        if source is None:
            raise HTTPException(status_code=422, detail="Selected invoice line does not belong to its delivery")
        so_item = await db.get(SalesOrderItem, source.sales_order_item_id)
        if so_item is None or so_item.sales_order_number != order.sales_order_number:
            raise HTTPException(status_code=422, detail="Delivery line does not match the Sales Order")
        if so_item.product_code != source.product_code or so_item.unit != source.unit:
            raise HTTPException(
                status_code=422, detail="Delivery product or unit no longer matches its Sales Order line"
            )
        try:
            require_whole_quantity(line_data.quantity, source.unit, "Invoice Quantity")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        already_billed = await billed_quantity(db, delivery.delivery_number, source.id, so_item.id)
        available = invoice_quantity_available(source.quantity, already_billed)
        if line_data.quantity > available:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Invoice quantity for delivery {delivery.delivery_number} exceeds the unbilled delivered quantity "
                    f"({available} {source.unit} available)"
                ),
            )
        amount = invoice_line_amount(line_data.quantity, so_item.unit_price)
        amounts.append(amount)
        requested_items.append(
            InvoiceItem(
                line_number=line_number,
                delivery_number=delivery.delivery_number,
                delivery_line_id=source.id,
                sales_order_number=order.sales_order_number,
                sales_order_item_id=so_item.id,
                product_code=so_item.product_code,
                part_name=so_item.part_name,
                part_no=so_item.part_no,
                description=so_item.description,
                lot_number=source.lot_number,
                quantity=line_data.quantity,
                unit=source.unit,
                unit_price=so_item.unit_price,
                amount=amount,
                remark=so_item.remark,
            )
        )
    if len(customer_codes) != 1:
        raise HTTPException(status_code=422, detail="One invoice may only contain deliveries for one customer")

    try:
        subtotal, tax_amount, grand_total = invoice_totals(amounts, data.discount_amount, data.tax_rate)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    customer_code = next(iter(customer_codes))
    customer = await db.get(Corporation, customer_code)
    if customer is None or not customer.is_customer:
        raise HTTPException(status_code=422, detail="Invoice customer is no longer active as a customer")
    invoice = Invoice(
        invoice_number=await generate_invoice_number(db, data.invoice_date),
        invoice_date=data.invoice_date,
        due_date=data.due_date,
        sales_order_number=data.sales_order_number,
        customer_code=customer.code,
        customer_name=customer.name,
        customer_address=customer.address,
        customer_phone=customer.phone_number,
        customer_contact_person=customer.contact_person_name,
        notes=data.notes,
        payment_terms=data.payment_terms,
        currency="IDR",
        subtotal=subtotal,
        discount_amount=data.discount_amount,
        tax_label=data.tax_label,
        tax_rate=data.tax_rate,
        tax_amount=tax_amount,
        grand_total=grand_total,
        status=InvoiceStatus.issued,
        created_by=current_user.id,
        created_by_name=f"{current_user.first_name} {current_user.last_name}".strip(),
        items=requested_items,
    )
    db.add(invoice)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Invoice could not be issued; reload deliveries and try again"
        ) from exc
    return invoice_response(await get_invoice(db, invoice.invoice_number))


@router.get("/{invoice_number}", response_model=InvoiceResponse)
async def get_invoice_detail(
    invoice_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceResponse:
    await current_access(db, current_user)
    return invoice_response(await get_invoice(db, invoice_number))


@router.get("/{invoice_number}/pdf")
async def download_invoice_pdf(
    invoice_number: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    await current_access(db, current_user)
    invoice = invoice_response(await get_invoice(db, invoice_number))
    content = invoice_pdf_bytes(invoice)
    safe_number = invoice.invoice_number.replace("/", "-")
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="invoice-{safe_number}.pdf"'},
    )


@router.post("/{invoice_number}/void", response_model=InvoiceResponse)
async def void_invoice(
    invoice_number: str,
    data: InvoiceVoidRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceResponse:
    await current_access(db, current_user)
    invoice = await get_invoice(db, invoice_number, lock=True)
    if invoice.status != InvoiceStatus.issued:
        raise HTTPException(status_code=409, detail="Only an issued invoice can be voided")
    invoice.status = InvoiceStatus.void
    invoice.voided_by = current_user.id
    invoice.voided_by_name = f"{current_user.first_name} {current_user.last_name}".strip()
    invoice.voided_at = datetime.now(timezone.utc)
    invoice.void_reason = data.reason
    await db.commit()
    return invoice_response(await get_invoice(db, invoice_number))
