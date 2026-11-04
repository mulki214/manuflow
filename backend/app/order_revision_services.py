from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Delivery,
    DeliveryLine,
    DeliveryStatus,
    OrderRevision,
    PurchaseOrder,
    SalesOrder,
    SalesOrderMaterialAllocation,
    SubcontractDispatch,
    SubcontractDispatchStatus,
    User,
)


async def sales_order_snapshot(db: AsyncSession, order: SalesOrder) -> dict[str, object]:
    item_ids = [item.id for item in order.items]
    dispatched_rows = await db.execute(
        select(DeliveryLine.sales_order_item_id, func.coalesce(func.sum(DeliveryLine.quantity), 0))
        .join(Delivery, Delivery.delivery_number == DeliveryLine.delivery_number)
        .where(Delivery.status == DeliveryStatus.dispatched, DeliveryLine.sales_order_item_id.in_(item_ids))
        .group_by(DeliveryLine.sales_order_item_id)
    )
    dispatched = {item_id: Decimal(str(amount)) for item_id, amount in dispatched_rows.all()}
    allocations = (
        (
            await db.execute(
                select(SalesOrderMaterialAllocation).where(
                    SalesOrderMaterialAllocation.sales_order_item_id.in_(item_ids)
                )
            )
        )
        .scalars()
        .all()
    )
    allocations_by_item: dict[int, list[dict[str, str]]] = {}
    for allocation in allocations:
        allocations_by_item.setdefault(allocation.sales_order_item_id, []).append(
            {
                "material_product_code": allocation.material_product_code,
                "required_quantity": str(allocation.required_quantity),
                "received_quantity": str(allocation.received_quantity),
                "unit": allocation.unit,
            }
        )
    return {
        "status": order.status.value,
        "fulfillment_status": order.fulfillment_status.value,
        "customer_code": order.customer_code,
        "customer_name": order.customer_name,
        "po_receipt_date": order.po_receipt_date.isoformat(),
        "customer_po_date": order.customer_po_date.isoformat(),
        "customer_po_number": order.customer_po_number,
        "delivery_date": order.delivery_date.isoformat(),
        "order_type": order.order_type.value,
        "notes": order.notes,
        "ship_to_name": order.ship_to_name,
        "ship_to_address": order.ship_to_address,
        "ship_to_contact_person": order.ship_to_contact_person,
        "ship_to_phone": order.ship_to_phone,
        "subtotal": str(order.subtotal),
        "grand_total": str(order.grand_total),
        "items": [
            {
                "id": item.id,
                "line_number": item.line_number,
                "product_code": item.product_code,
                "part_name": item.part_name,
                "quantity": str(item.quantity_grams),
                "unit": item.unit,
                "delivered_quantity": str(item.delivered_quantity),
                "in_transit_quantity": str(dispatched.get(item.id, Decimal("0"))),
                "outstanding_quantity": str(max(item.quantity_grams - item.delivered_quantity, Decimal("0"))),
                "excess_delivery_quantity": str(max(item.delivered_quantity - item.quantity_grams, Decimal("0"))),
                "unit_price": str(item.unit_price),
                "amount": str(item.amount),
                "remark": item.remark,
                "outstanding_note": item.outstanding_note,
                "material_allocations": allocations_by_item.get(item.id, []),
            }
            for item in order.items
        ],
    }


async def purchase_order_snapshot(db: AsyncSession, order: PurchaseOrder) -> dict[str, object]:
    item_ids = [item.id for item in order.items]
    dispatch_rows = await db.execute(
        select(
            SubcontractDispatch.purchase_order_item_id,
            func.coalesce(
                func.sum(SubcontractDispatch.expected_output_quantity - SubcontractDispatch.returned_quantity), 0
            ),
        )
        .where(
            SubcontractDispatch.status != SubcontractDispatchStatus.reversed,
            SubcontractDispatch.purchase_order_item_id.in_(item_ids),
        )
        .group_by(SubcontractDispatch.purchase_order_item_id)
    )
    in_transit = {item_id: max(Decimal(str(amount)), Decimal("0")) for item_id, amount in dispatch_rows.all()}
    return {
        "status": order.status.value,
        "fulfillment_status": order.fulfillment_status.value,
        "sales_order_number": order.sales_order_number,
        "supplier_code": order.supplier_code,
        "supplier_name": order.supplier_name,
        "po_date": order.po_date.isoformat(),
        "requested_delivery_date": order.requested_delivery_date.isoformat(),
        "delivery_plant_code": order.delivery_plant_code,
        "delivery_plant_name": order.delivery_plant_name,
        "order_kind": order.order_kind.value,
        "quotation_reference": order.quotation_reference,
        "quotation_date": order.quotation_date.isoformat() if order.quotation_date else None,
        "payment_terms_days": order.payment_terms_days,
        "payment_due_date": order.payment_due_date.isoformat(),
        "discount_amount": str(order.discount_amount),
        "ppn_rate": str(order.ppn_rate),
        "ppn_amount": str(order.ppn_amount),
        "pph23_rate": str(order.pph23_rate),
        "pph23_amount": str(order.pph23_amount),
        "notes": order.notes,
        "subtotal": str(order.subtotal),
        "grand_total": str(order.grand_total),
        "items": [
            {
                "id": item.id,
                "line_number": item.line_number,
                "product_code": item.product_code,
                "part_name": item.part_name,
                "quantity": str(item.quantity_grams),
                "unit": item.unit,
                "received_quantity": str(item.received_quantity),
                "in_transit_quantity": str(in_transit.get(item.id, Decimal("0"))),
                "outstanding_quantity": str(max(item.quantity_grams - item.received_quantity, Decimal("0"))),
                "excess_quantity": str(max(item.received_quantity - item.quantity_grams, Decimal("0"))),
                "unit_price": str(item.unit_price),
                "amount": str(item.amount),
                "remark": item.remark,
                "process_from_code": item.process_from_code,
                "process_to_code": item.process_to_code,
            }
            for item in order.items
        ],
    }


async def append_order_revision(
    db: AsyncSession,
    *,
    order_type: str,
    order_number: str,
    reason: str,
    user: User,
    before_snapshot: dict[str, object],
    after_snapshot: dict[str, object],
) -> None:
    if before_snapshot == after_snapshot:
        return
    last_revision = await db.scalar(
        select(func.max(OrderRevision.revision_number)).where(
            OrderRevision.order_type == order_type,
            OrderRevision.order_number == order_number,
        )
    )
    changed_by_name = f"{user.first_name} {user.last_name}".strip() or user.id
    db.add(
        OrderRevision(
            order_type=order_type,
            order_number=order_number,
            revision_number=(last_revision or 0) + 1,
            reason=reason,
            changed_by=user.id,
            changed_by_name=changed_by_name,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )
    )
