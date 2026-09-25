from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.document_services import quotation_pdf_bytes
from app.models import Corporation, Department, Product, Quotation, QuotationItem, User
from app.module_permissions import DepartmentModuleAccess, ensure_department_access, resolve_department_access
from app.quotation_services import calculate_quotation_line_amount, calculate_quotation_totals, generate_quotation_number
from app.schemas import (
    PaginatedQuotations,
    QuotationCreate,
    QuotationItemResponse,
    QuotationResponse,
    QuotationUpdate,
)

router = APIRouter(prefix="/quotations", tags=["Quotation"])


async def current_access(db: AsyncSession, user: User) -> DepartmentModuleAccess:
    department = await db.get(Department, settings.sales_department_code)
    access = resolve_department_access(user, department)
    ensure_department_access(access, "Sales")
    return access


async def get_quotation(db: AsyncSession, number: str) -> Quotation:
    quotation = (
        await db.execute(
            select(Quotation).options(selectinload(Quotation.items)).where(Quotation.quotation_number == number)
        )
    ).scalar_one_or_none()
    if quotation is None:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return quotation


async def quotation_response(db: AsyncSession, quotation: Quotation) -> QuotationResponse:
    creator = await db.get(User, quotation.created_by)
    creator_name = f"{creator.first_name} {creator.last_name}".strip() if creator else quotation.created_by
    return QuotationResponse(
        quotation_number=quotation.quotation_number,
        quotation_date=quotation.quotation_date,
        valid_until=quotation.valid_until,
        customer_code=quotation.customer_code,
        customer_name=quotation.customer_name,
        customer_address=quotation.customer_address,
        customer_phone=quotation.customer_phone,
        customer_contact_person=quotation.customer_contact_person,
        notes=quotation.notes,
        payment_terms=quotation.payment_terms,
        currency=quotation.currency,
        subtotal=quotation.subtotal,
        discount_amount=quotation.discount_amount,
        tax_label=quotation.tax_label,
        tax_rate=quotation.tax_rate,
        tax_amount=quotation.tax_amount,
        grand_total=quotation.grand_total,
        created_by=quotation.created_by,
        created_by_name=creator_name,
        items=[QuotationItemResponse.model_validate(item) for item in quotation.items],
        created_at=quotation.created_at,
        updated_at=quotation.updated_at,
    )


async def apply_data(db: AsyncSession, quotation: Quotation, data: QuotationCreate | QuotationUpdate) -> None:
    customer = await db.get(Corporation, data.customer_code)
    if customer is None or not customer.is_customer:
        raise HTTPException(status_code=422, detail="Selected corporation is not a customer")
    new_items: list[QuotationItem] = []
    amounts: list[Decimal] = []
    for line_number, item_data in enumerate(data.items, start=1):
        product = await db.get(Product, item_data.product_code)
        if product is None:
            raise HTTPException(status_code=422, detail=f"Product {item_data.product_code} does not exist")
        amount = calculate_quotation_line_amount(item_data.quantity, item_data.unit_price)
        amounts.append(amount)
        new_items.append(
            QuotationItem(
                line_number=line_number,
                product_code=product.code,
                part_name=product.part_name,
                part_no=product.part_no,
                description=product.description,
                quantity=item_data.quantity,
                unit=item_data.unit.value,
                unit_price=item_data.unit_price,
                amount=amount,
                remark=item_data.remark,
            )
        )
    subtotal, tax_amount, grand_total = calculate_quotation_totals(amounts, data.discount_amount, data.tax_rate)
    quotation.quotation_date = data.quotation_date
    quotation.valid_until = data.valid_until
    quotation.customer_code = customer.code
    quotation.customer_name = customer.name
    quotation.customer_address = customer.address
    quotation.customer_phone = customer.phone_number
    quotation.customer_contact_person = customer.contact_person_name
    quotation.notes = data.notes
    quotation.payment_terms = data.payment_terms
    quotation.currency = "IDR"
    quotation.subtotal = subtotal
    quotation.discount_amount = data.discount_amount
    quotation.tax_label = data.tax_label
    quotation.tax_rate = data.tax_rate
    quotation.tax_amount = tax_amount
    quotation.grand_total = grand_total
    quotation.items = new_items


@router.get("", response_model=PaginatedQuotations)
async def list_quotations(
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), search: str | None = None,
    from_date: date | None = None, to_date: date | None = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
) -> PaginatedQuotations:
    await current_access(db, current_user)
    filters = [Quotation.department_code == settings.sales_department_code]
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(Quotation.quotation_number.ilike(term), Quotation.customer_name.ilike(term), Quotation.customer_code.ilike(term)))
    if from_date:
        filters.append(Quotation.quotation_date >= from_date)
    if to_date:
        filters.append(Quotation.quotation_date <= to_date)
    total = (await db.scalar(select(func.count()).select_from(Quotation).where(*filters))) or 0
    rows = list((await db.execute(select(Quotation).options(selectinload(Quotation.items)).where(*filters).order_by(Quotation.quotation_date.desc(), Quotation.quotation_number.desc()).offset((page - 1) * size).limit(size))).scalars())
    return PaginatedQuotations(items=[await quotation_response(db, item) for item in rows], total=total, page=page, size=size)


@router.post("", response_model=QuotationResponse, status_code=status.HTTP_201_CREATED)
async def create_quotation(data: QuotationCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> QuotationResponse:
    await current_access(db, current_user)
    quotation = Quotation(
        quotation_number=await generate_quotation_number(db, data.quotation_date),
        quotation_date=data.quotation_date, valid_until=data.valid_until, customer_code=data.customer_code,
        customer_name="", customer_address="", customer_phone="", customer_contact_person="", subtotal=Decimal("0"),
        grand_total=Decimal("0"), department_code=settings.sales_department_code, created_by=current_user.id,
    )
    await apply_data(db, quotation, data)
    db.add(quotation)
    await db.commit()
    return await quotation_response(db, await get_quotation(db, quotation.quotation_number))


@router.get("/{quotation_number}", response_model=QuotationResponse)
async def read_quotation(quotation_number: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> QuotationResponse:
    await current_access(db, current_user)
    return await quotation_response(db, await get_quotation(db, quotation_number))


@router.patch("/{quotation_number}", response_model=QuotationResponse)
async def update_quotation(quotation_number: str, data: QuotationUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> QuotationResponse:
    await current_access(db, current_user)
    quotation = await get_quotation(db, quotation_number)
    await apply_data(db, quotation, data)
    await db.commit()
    return await quotation_response(db, await get_quotation(db, quotation_number))


@router.delete("/{quotation_number}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_quotation(quotation_number: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    await current_access(db, current_user)
    await db.delete(await get_quotation(db, quotation_number))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{quotation_number}/pdf")
async def download_quotation_pdf(quotation_number: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> StreamingResponse:
    await current_access(db, current_user)
    quotation = await quotation_response(db, await get_quotation(db, quotation_number))
    content = quotation_pdf_bytes(quotation)
    return StreamingResponse(iter([content]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="quotation-{quotation_number}.pdf"'})
