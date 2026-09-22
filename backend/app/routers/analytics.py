from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.document_services import excel_bytes
from app.models import (
    Delivery,
    FinishGoodReceipt,
    Product,
    ProductionExecution,
    ProductLot,
    ProductProcessStandard,
    PurchaseOrder,
    PurchaseOrderItem,
    QualityInspection,
    SalesOrder,
    SalesOrderItem,
    WipLotJob,
    WipLotStatus,
)
from app.production_services import effective_target_cycle_time

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
reporting_router = APIRouter(prefix="/reporting", tags=["Reporting"])


@dashboard_router.get("")
async def dashboard(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
) -> dict:
    async def count(model, *filters):
        return (await db.scalar(select(func.count()).select_from(model).where(*filters))) or 0

    performance_to = to_date or date.today()
    performance_from = from_date or performance_to - timedelta(days=6)
    if performance_from > performance_to:
        raise HTTPException(status_code=422, detail="From date must not be after to date")
    if (performance_to - performance_from).days > 6:
        raise HTTPException(status_code=422, detail="Dashboard performance range cannot exceed 7 days")

    standards = list(
        (
            await db.execute(
                select(ProductProcessStandard)
                .where(ProductProcessStandard.is_active.is_(True))
                .order_by(ProductProcessStandard.product_code, ProductProcessStandard.process_code)
            )
        ).scalars()
    )
    standards_by_machine = {(row.product_code, row.process_code, row.machine_code): row for row in standards}
    product_targets = {
        code: target
        for code, target in (await db.execute(select(Product.code, Product.default_cycle_time_seconds))).all()
    }
    executions = list(
        (
            await db.execute(
                select(ProductionExecution)
                .where(
                    ProductionExecution.process_date >= performance_from,
                    ProductionExecution.process_date <= performance_to,
                )
                .order_by(ProductionExecution.product_code, ProductionExecution.before_process_code)
            )
        ).scalars()
    )
    performance: dict[tuple[str, str], dict] = {}
    for execution in executions:
        actual_cycle = execution.observed_cycle_time_seconds or execution.cycle_time_seconds
        standard = standards_by_machine.get(
            (execution.product_code, execution.before_process_code, execution.machine_code)
        ) or standards_by_machine.get((execution.product_code, execution.before_process_code, None))
        target_cycle = effective_target_cycle_time(
            product_targets.get(execution.product_code),
            standard.target_cycle_time_seconds if standard else None,
        )
        if not target_cycle or not actual_cycle or actual_cycle <= 0:
            continue
        quantity = execution.good_quantity if execution.good_quantity > 0 else execution.processing_quantity
        if quantity <= 0:
            continue
        key = (execution.product_code, execution.before_process_code)
        metric = performance.setdefault(
            key,
            {
                "product_code": execution.product_code,
                "product_name": execution.product_name,
                "process_code": execution.before_process_code,
                "target_seconds": Decimal("0"),
                "actual_seconds": Decimal("0"),
                "quantity": Decimal("0"),
                "execution_count": 0,
            },
        )
        metric["target_seconds"] += target_cycle * quantity
        metric["actual_seconds"] += actual_cycle * quantity
        metric["quantity"] += quantity
        metric["execution_count"] += 1

    performance_items = []
    for metric in performance.values():
        quantity = metric["quantity"]
        performance_items.append(
            {
                "product_code": metric["product_code"],
                "product_name": metric["product_name"],
                "process_code": metric["process_code"],
                "target_cycle_time_seconds": (metric["target_seconds"] / quantity).quantize(Decimal("0.001")),
                "actual_cycle_time_seconds": (metric["actual_seconds"] / quantity).quantize(Decimal("0.001")),
                "performance_percent": (metric["target_seconds"] / metric["actual_seconds"] * 100).quantize(
                    Decimal("0.1")
                ),
                "execution_count": metric["execution_count"],
            }
        )
    return {
        "sales_orders": {
            "total": await count(SalesOrder),
            "open": await count(SalesOrder, SalesOrder.fulfillment_status == "open"),
        },
        "wip": {
            "production": await count(WipLotJob, WipLotJob.status.in_([WipLotStatus.queued, WipLotStatus.in_process])),
            "quality": await count(WipLotJob, WipLotJob.status == WipLotStatus.awaiting_qc),
            "finish_good_queue": await count(WipLotJob, WipLotJob.status == WipLotStatus.awaiting_finish_goods),
            "ng": await count(WipLotJob, WipLotJob.status == WipLotStatus.ng),
        },
        "finish_goods": await count(FinishGoodReceipt),
        "deliveries": await count(Delivery),
        "production_performance": {
            "from_date": performance_from,
            "to_date": performance_to,
            "items": performance_items,
        },
    }


@reporting_router.get("/stock")
async def stock_report(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)) -> list[dict]:
    rows = await db.execute(
        select(
            ProductLot.product_code,
            ProductLot.lot_number,
            ProductLot.plant_code,
            ProductLot.storage_location_code,
            ProductLot.unit,
            func.sum(ProductLot.current_quantity_grams),
        ).group_by(
            ProductLot.product_code,
            ProductLot.lot_number,
            ProductLot.plant_code,
            ProductLot.storage_location_code,
            ProductLot.unit,
        )
    )
    return [
        {
            "product_code": r[0],
            "lot_number": r[1],
            "plant_code": r[2],
            "storage_location_code": r[3],
            "unit": r[4],
            "quantity": r[5],
        }
        for r in rows.all()
    ]


@reporting_router.get("/stock/export-excel")
async def export_stock_report(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)) -> StreamingResponse:
    records = await stock_report(db, _)
    content = excel_bytes(
        "Stock by Lot",
        ["Product", "Lot", "Quantity", "Unit", "Plant", "Storage Location"],
        [
            [
                row["product_code"],
                row["lot_number"],
                float(row["quantity"]),
                row["unit"],
                row["plant_code"],
                row["storage_location_code"],
            ]
            for row in records
        ],
    )
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="stock-by-lot.xlsx"'},
    )


def _plain(value):
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


async def _operational_report(
    report_type: str,
    db: AsyncSession,
    date_from: date | None,
    date_to: date | None,
) -> list[dict]:
    if report_type in {"production", "machine", "operator"}:
        filters = []
        if date_from:
            filters.append(ProductionExecution.process_date >= date_from)
        if date_to:
            filters.append(ProductionExecution.process_date <= date_to)
        executions = list((await db.execute(select(ProductionExecution).where(*filters))).scalars())
        if report_type == "production":
            return [
                {
                    "production_number": row.production_number,
                    "date": row.process_date,
                    "shift": row.shift,
                    "product": row.product_code,
                    "lot": row.lot_number,
                    "process": row.before_process_name,
                    "machine": row.machine_name or "-",
                    "operator": row.performed_by_name,
                    "processed": row.processing_quantity,
                    "good": row.good_quantity,
                    "repair": row.repair_quantity,
                    "ng": row.ng_quantity,
                    "unit": row.unit,
                    "started_at": row.started_at,
                    "ended_at": row.ended_at,
                    "cycle_time_seconds": row.cycle_time_seconds,
                    "ng_override": row.ng_limit_exceeded,
                }
                for row in executions
            ]
        key_name = "machine" if report_type == "machine" else "operator"
        grouped: dict[str, dict] = {}
        for row in executions:
            key = (row.machine_name or "Unassigned") if report_type == "machine" else row.performed_by_name
            item = grouped.setdefault(
                key,
                {key_name: key, "executions": 0, "processed": Decimal("0"), "good": Decimal("0"), "ng": Decimal("0")},
            )
            item["executions"] += 1
            item["processed"] += row.processing_quantity
            item["good"] += row.good_quantity
            item["ng"] += row.ng_quantity
        return list(grouped.values())
    if report_type == "quality":
        filters = []
        if date_from:
            filters.append(QualityInspection.inspection_date >= date_from)
        if date_to:
            filters.append(QualityInspection.inspection_date <= date_to)
        records = list((await db.execute(select(QualityInspection).where(*filters))).scalars())
        return [
            {
                "quality_number": row.quality_number,
                "date": row.inspection_date,
                "shift": row.shift,
                "product": row.product_code,
                "lot": row.lot_number,
                "before_process": row.before_process_name,
                "inspected": row.inspection_quantity,
                "passed": row.pass_quantity,
                "repair": row.repair_quantity,
                "ng": row.ng_quantity,
                "unit": row.unit,
                "problem": row.problem,
                "inspector": row.performed_by_name,
                "ng_override": row.ng_limit_exceeded,
            }
            for row in records
        ]
    if report_type == "sales-order-fulfillment":
        filters = []
        if date_from:
            filters.append(SalesOrder.po_receipt_date >= date_from)
        if date_to:
            filters.append(SalesOrder.po_receipt_date <= date_to)
        records = (
            await db.execute(
                select(SalesOrder, SalesOrderItem)
                .join(SalesOrderItem, SalesOrderItem.sales_order_number == SalesOrder.sales_order_number)
                .where(*filters)
                .order_by(SalesOrder.po_receipt_date.desc(), SalesOrderItem.line_number)
            )
        ).all()
        return [
            {
                "sales_order": order.sales_order_number,
                "customer_po": order.customer_po_number,
                "customer": order.customer_name,
                "product": item.product_code,
                "description": item.description,
                "ordered": item.quantity_grams,
                "delivered": item.delivered_quantity,
                "outstanding": max(item.quantity_grams - item.delivered_quantity, Decimal("0")),
                "unit": item.unit,
                "fulfillment_status": order.fulfillment_status,
                "outstanding_note": item.outstanding_note,
            }
            for order, item in records
        ]
    if report_type == "purchase-order":
        filters = []
        if date_from:
            filters.append(PurchaseOrder.po_date >= date_from)
        if date_to:
            filters.append(PurchaseOrder.po_date <= date_to)
        records = (
            await db.execute(
                select(PurchaseOrder, PurchaseOrderItem)
                .join(PurchaseOrderItem, PurchaseOrderItem.purchase_order_number == PurchaseOrder.po_number)
                .where(*filters)
                .order_by(PurchaseOrder.po_date.desc(), PurchaseOrderItem.line_number)
            )
        ).all()
        return [
            {
                "purchase_order": order.po_number,
                "date": order.po_date,
                "supplier": order.supplier_name,
                "product": item.product_code,
                "description": item.description,
                "ordered": item.quantity_grams,
                "received": item.received_quantity,
                "outstanding": max(item.quantity_grams - item.received_quantity, Decimal("0")),
                "unit": item.unit,
                "approval_status": order.status,
                "fulfillment_status": order.fulfillment_status,
            }
            for order, item in records
        ]
    raise HTTPException(status_code=404, detail="Report type not found")


@reporting_router.get("/{report_type}")
async def operational_report(
    report_type: str,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
) -> list[dict]:
    if report_type == "stock":
        return await stock_report(db, _)
    records = await _operational_report(report_type, db, date_from, date_to)
    return [{key: _plain(value) for key, value in row.items()} for row in records]


@reporting_router.get("/{report_type}/export-excel")
async def export_operational_report(
    report_type: str,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
) -> StreamingResponse:
    records = await operational_report(report_type, date_from, date_to, db, _)
    headers = list(records[0].keys()) if records else ["message"]
    rows = [[row.get(header) for header in headers] for row in records] if records else [["No records"]]
    content = excel_bytes(report_type.replace("-", " ").title(), [h.replace("_", " ").title() for h in headers], rows)
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{report_type}.xlsx"'},
    )
