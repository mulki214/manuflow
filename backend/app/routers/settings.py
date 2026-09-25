from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    AccessLevel, DailyStockRebalancingSequence, InventoryMovement,
    InventoryMovementType, Product, ProductLot, StockRebalancing,
    StockRebalancingLine, User,
)
from app.operational_services import require_whole_quantity
from app.schemas import (
    PaginatedStockRebalances, StockRebalanceCreate, StockRebalanceLineResponse,
    StockRebalanceLotResponse, StockRebalanceResponse,
)

router = APIRouter(prefix="/settings", tags=["Settings"])


def assert_administrator(user: User) -> None:
    if user.access_level != AccessLevel.administrator:
        raise HTTPException(status_code=403, detail="Stock rebalancing is restricted to System Administrators")


def user_name(user: User | None, fallback: str) -> str:
    return f"{user.first_name} {user.last_name}".strip() if user else fallback


async def next_number(db: AsyncSession, rebalance_date) -> str:
    value = (await db.execute(
        insert(DailyStockRebalancingSequence)
        .values(sequence_date=rebalance_date, last_value=0)
        .on_conflict_do_update(
            index_elements=[DailyStockRebalancingSequence.sequence_date],
            set_={"last_value": DailyStockRebalancingSequence.last_value + 1},
        )
        .returning(DailyStockRebalancingSequence.last_value)
    )).scalar_one()
    if value > 999:
        raise HTTPException(status_code=409, detail="The daily stock rebalancing limit of 999 has been reached")
    return f"RB-{rebalance_date:%y%m%d}-{value:03d}"


async def response(db: AsyncSession, record: StockRebalancing) -> StockRebalanceResponse:
    creator = await db.get(User, record.created_by)
    return StockRebalanceResponse(
        rebalance_number=record.rebalance_number,
        rebalance_date=record.rebalance_date,
        notes=record.notes,
        created_by=record.created_by,
        created_by_name=user_name(creator, record.created_by),
        created_at=record.created_at,
        lines=[StockRebalanceLineResponse.model_validate(line) for line in record.lines],
    )


async def get_rebalance(db: AsyncSession, number: str) -> StockRebalancing:
    record = (await db.execute(
        select(StockRebalancing).options(selectinload(StockRebalancing.lines))
        .where(StockRebalancing.rebalance_number == number)
    )).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Stock rebalancing not found")
    return record


@router.get("/stock-rebalancing/lots", response_model=list[StockRebalanceLotResponse])
async def list_rebalance_lots(
    search: str | None = None,
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[StockRebalanceLotResponse]:
    assert_administrator(current_user)
    filters = []
    if search and search.strip():
        value = f"%{search.strip()}%"
        filters.append(or_(ProductLot.lot_number.ilike(value), ProductLot.product_code.ilike(value), Product.part_name.ilike(value)))
    rows = (await db.execute(
        select(ProductLot, Product).join(Product, Product.code == ProductLot.product_code)
        .where(*filters).order_by(Product.part_name, ProductLot.lot_number).limit(limit)
    )).all()
    return [StockRebalanceLotResponse(
        id=lot.id, product_code=lot.product_code, product_name=product.part_name,
        description=product.description, lot_number=lot.lot_number, plant_code=lot.plant_code,
        storage_location_code=lot.storage_location_code, unit=lot.unit,
        current_quantity=lot.current_quantity_grams,
    ) for lot, product in rows]


@router.get("/stock-rebalancing", response_model=PaginatedStockRebalances)
async def list_rebalances(
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), search: str | None = None,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user),
) -> PaginatedStockRebalances:
    assert_administrator(current_user)
    filters = [StockRebalancing.rebalance_number.ilike(f"%{search.strip()}%")] if search and search.strip() else []
    records = list((await db.execute(
        select(StockRebalancing).options(selectinload(StockRebalancing.lines)).where(*filters)
        .order_by(StockRebalancing.created_at.desc()).offset((page - 1) * size).limit(size)
    )).scalars())
    total = await db.scalar(select(func.count()).select_from(StockRebalancing).where(*filters))
    return PaginatedStockRebalances(items=[await response(db, item) for item in records], total=total or 0, page=page, size=size)


@router.get("/stock-rebalancing/{number}", response_model=StockRebalanceResponse)
async def read_rebalance(number: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> StockRebalanceResponse:
    assert_administrator(current_user)
    return await response(db, await get_rebalance(db, number))


@router.post("/stock-rebalancing", response_model=StockRebalanceResponse, status_code=status.HTTP_201_CREATED)
async def create_rebalance(data: StockRebalanceCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> StockRebalanceResponse:
    assert_administrator(current_user)
    record = StockRebalancing(
        rebalance_number=await next_number(db, data.rebalance_date), rebalance_date=data.rebalance_date,
        notes=data.notes.strip(), created_by=current_user.id,
    )
    # Lock rows in a stable order so concurrent stock actions cannot overwrite a count.
    inputs = sorted(data.lines, key=lambda line: line.lot_id)
    for line_number, item in enumerate(inputs, 1):
        lot = (await db.execute(select(ProductLot).where(ProductLot.id == item.lot_id).with_for_update())).scalar_one_or_none()
        if not lot:
            raise HTTPException(status_code=422, detail=f"Lot {item.lot_id} was not found")
        product = (await db.execute(select(Product).where(Product.code == lot.product_code).with_for_update())).scalar_one()
        try:
            require_whole_quantity(item.physical_quantity, lot.unit, "Physical quantity")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        system_quantity = Decimal(lot.current_quantity_grams)
        physical_quantity = Decimal(item.physical_quantity)
        difference = physical_quantity - system_quantity
        product_after = Decimal(product.current_stock_grams) + difference
        if product_after < 0:
            raise HTTPException(status_code=422, detail=f"Rebalancing {product.part_name} would make product stock negative")
        lot.current_quantity_grams = physical_quantity
        product.current_stock_grams = product_after
        record.lines.append(StockRebalancingLine(
            line_number=line_number, lot_id=lot.id, product_code=product.code, product_name=product.part_name,
            lot_number=lot.lot_number, plant_code=lot.plant_code, storage_location_code=lot.storage_location_code,
            unit=lot.unit, system_quantity=system_quantity, physical_quantity=physical_quantity,
            difference_quantity=difference, lot_quantity_after=physical_quantity,
            product_stock_after=product_after, reason=item.reason.strip(), notes=item.notes.strip(),
        ))
        if difference:
            db.add(InventoryMovement(
                movement_date=datetime.now().astimezone(),
                movement_type=InventoryMovementType.stock_rebalance_in if difference > 0 else InventoryMovementType.stock_rebalance_out,
                product_code=product.code, lot_id=lot.id, unit=lot.unit, quantity_grams=difference,
                product_stock_after_grams=product_after, lot_stock_after_grams=physical_quantity,
                reference_type="stock_rebalancing", reference_number=record.rebalance_number,
                performed_by=current_user.id, notes=f"{item.reason.strip()}: {item.notes.strip()}".strip(": "),
            ))
    db.add(record)
    await db.commit()
    return await response(db, await get_rebalance(db, record.rebalance_number))
