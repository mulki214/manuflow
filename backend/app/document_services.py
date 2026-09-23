from datetime import datetime
from io import BytesIO
from typing import Any

import jwt
from openpyxl import Workbook

from app.config import settings


def signed_document_payload(
    document_type: str,
    document_number: str,
    action: str,
    user_id: str,
    user_name: str,
    occurred_at: datetime,
) -> str:
    return jwt.encode(
        {
            "document_type": document_type,
            "document_number": document_number,
            "action": action,
            "user_id": user_id,
            "user_name": user_name,
            "occurred_at": occurred_at.isoformat(),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def verify_document_payload(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def excel_bytes(title: str, headers: list[str], rows: list[list[Any]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title[:31]
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        width = min(max(len(str(cell.value or "")) for cell in column) + 2, 45)
        sheet.column_dimensions[column[0].column_letter].width = width
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def purchase_order_pdf_bytes(order: Any) -> bytes:
    """Render a printable PO with line items and signatures below the totals."""
    import qrcode
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table

    stream = BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"Purchase Order {order.po_number}",
    )
    styles = getSampleStyleSheet()
    center = ParagraphStyle("center", parent=styles["Normal"], alignment=TA_CENTER)
    right = ParagraphStyle("right", parent=styles["Normal"], alignment=TA_RIGHT)
    story = [
        Paragraph("<b>PURCHASE ORDER</b>", styles["Title"]),
        Paragraph(f"<b>{order.po_number}</b>", center),
        Spacer(1, 5 * mm),
        Table(
            [
                ["PO Date", order.po_date.strftime("%d/%m/%Y"), "Supplier", order.supplier_name],
                [
                    "Plant",
                    order.delivery_plant_name,
                    "Requested Delivery",
                    order.requested_delivery_date.strftime("%d/%m/%Y"),
                ],
                ["Address", order.delivery_address, "Quotation", order.quotation_reference or "-"],
            ],
            colWidths=[28 * mm, 55 * mm, 35 * mm, 60 * mm],
            style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.3, colors.grey)],
        ),
        Spacer(1, 5 * mm),
    ]
    item_rows = [["No", "Product", "Description", "Qty", "Unit", "Price", "Amount"]]
    for item in order.items:
        item_rows.append(
            [
                item.line_number,
                item.product_code,
                Paragraph(item.description, styles["BodyText"]),
                f"{item.quantity_grams:,.3f}",
                "grams" if item.unit == "gram" else item.unit,
                f"{item.unit_price:,.2f}",
                f"{item.amount:,.2f}",
            ]
        )
    story.append(
        Table(
            item_rows,
            repeatRows=1,
            colWidths=[9 * mm, 22 * mm, 58 * mm, 20 * mm, 17 * mm, 27 * mm, 29 * mm],
            style=[
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F659F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
            ],
        )
    )
    story.extend(
        [
            Spacer(1, 4 * mm),
            Table(
                [
                    ["Subtotal", Paragraph(f"{order.currency} {order.subtotal:,.2f}", right)],
                    ["Discount", Paragraph(f"{order.currency} {order.discount_amount:,.2f}", right)],
                    [f"PPN ({order.ppn_rate}%)", Paragraph(f"{order.currency} {order.ppn_amount:,.2f}", right)],
                    [f"PPh 23 ({order.pph23_rate}%)", Paragraph(f"{order.currency} -{order.pph23_amount:,.2f}", right)],
                    [
                        Paragraph("<b>Grand Total</b>", styles["Normal"]),
                        Paragraph(f"<b>{order.currency} {order.grand_total:,.2f}</b>", right),
                    ],
                ],
                colWidths=[40 * mm, 55 * mm],
                hAlign="RIGHT",
                style=[("LINEABOVE", (0, -1), (-1, -1), 0.7, colors.black)],
            ),
            Spacer(1, 9 * mm),
        ]
    )

    def qr_image(payload: str | None) -> Any:
        if not payload:
            return Paragraph("Pending approval", center)
        image_stream = BytesIO()
        qrcode.make(payload).save(image_stream, format="PNG")
        image_stream.seek(0)
        return Image(image_stream, width=25 * mm, height=25 * mm)

    signature_rows = [
        [Paragraph("<b>Created By</b>", center), Paragraph("<b>Approved By</b>", center)],
        [qr_image(order.creator_qr_payload), qr_image(order.approval_qr_payload)],
        [Paragraph(order.created_by_name, center), Paragraph(order.reviewed_by_name or "-", center)],
    ]
    story.append(
        Table(
            signature_rows,
            colWidths=[65 * mm, 65 * mm],
            hAlign="CENTER",
            style=[("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")],
        )
    )
    document.build(story)
    return stream.getvalue()


def purchase_request_pdf_bytes(request: Any) -> bytes:
    """Printable Purchase Request with verifiable submit/review QR signatures."""
    import qrcode
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table

    stream = BytesIO()
    document = SimpleDocTemplate(stream, pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    styles = getSampleStyleSheet()
    center = ParagraphStyle("pr-center", parent=styles["Normal"], alignment=TA_CENTER)
    story = [Paragraph("<b>PURCHASE REQUEST</b>", styles["Title"]), Paragraph(f"<b>{request.request_number}</b>", center), Spacer(1, 5 * mm)]
    story.append(Table([["Date", request.request_date.strftime("%d/%m/%Y"), "Status", request.status], ["Requested By", request.created_by_name, "Department", request.department_code or "-"], ["Notes", request.notes or "-", "Reviewed By", request.reviewed_by_name or "Pending review"]], colWidths=[28 * mm, 55 * mm, 35 * mm, 60 * mm], style=[("GRID", (0, 0), (-1, -1), .3, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    rows = [["No", "Product", "Description", "Qty", "Unit", "Remark"]]
    for item in request.items:
        rows.append([item.line_number, item.product_code, Paragraph(item.description, styles["BodyText"]), f"{item.quantity:,.3f}", item.unit, item.remark])
    story.extend([Spacer(1, 5 * mm), Table(rows, repeatRows=1, colWidths=[10 * mm, 27 * mm, 62 * mm, 22 * mm, 18 * mm, 39 * mm], style=[("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F659F")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), .3, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")])])
    def qr(payload: str | None):
        if not payload: return Paragraph("Pending review", center)
        image = BytesIO(); qrcode.make(payload).save(image, format="PNG"); image.seek(0)
        return Image(image, width=25 * mm, height=25 * mm)
    story.extend([Spacer(1, 9 * mm), Table([[Paragraph("<b>Submitted By</b>", center), Paragraph("<b>Reviewed By</b>", center)], [qr(request.creator_qr_payload), qr(request.review_qr_payload)], [Paragraph(request.created_by_name, center), Paragraph(request.reviewed_by_name or "-", center)]], colWidths=[65 * mm, 65 * mm], hAlign="CENTER", style=[("ALIGN", (0, 0), (-1, -1), "CENTER")])])
    document.build(story)
    return stream.getvalue()


def sales_order_pdf_bytes(order: Any) -> bytes:
    """Render a printable Sales Order using the same signature layout as PO."""
    import qrcode
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table

    stream = BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"Sales Order {order.sales_order_number}",
    )
    styles = getSampleStyleSheet()
    center = ParagraphStyle("so-center", parent=styles["Normal"], alignment=TA_CENTER)
    right = ParagraphStyle("so-right", parent=styles["Normal"], alignment=TA_RIGHT)
    story = [
        Paragraph("<b>SALES ORDER</b>", styles["Title"]),
        Paragraph(f"<b>{order.sales_order_number}</b>", center),
        Spacer(1, 5 * mm),
        Table(
            [
                ["PO Receipt", order.po_receipt_date.strftime("%d/%m/%Y"), "Customer", order.customer_name],
                ["Customer PO", order.customer_po_number, "Delivery", order.delivery_date.strftime("%d/%m/%Y")],
                ["Ship To", order.ship_to_name, "Address", Paragraph(order.ship_to_address, styles["BodyText"])],
            ],
            colWidths=[28 * mm, 55 * mm, 35 * mm, 60 * mm],
            style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.3, colors.grey)],
        ),
        Spacer(1, 5 * mm),
    ]
    rows = [["No", "Product", "Description", "Qty", "Unit", "Price", "Amount"]]
    for item in order.items:
        rows.append(
            [
                item.line_number,
                item.product_code,
                Paragraph(item.description, styles["BodyText"]),
                f"{item.quantity_grams:,.3f}",
                "grams" if item.unit == "gram" else item.unit,
                f"{item.unit_price:,.2f}",
                f"{item.amount:,.2f}",
            ]
        )
    story.append(
        Table(
            rows,
            repeatRows=1,
            colWidths=[9 * mm, 22 * mm, 58 * mm, 20 * mm, 17 * mm, 27 * mm, 29 * mm],
            style=[
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F659F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
            ],
        )
    )
    story.extend(
        [
            Spacer(1, 4 * mm),
            Table(
                [
                    [
                        Paragraph("<b>Grand Total</b>", styles["Normal"]),
                        Paragraph(f"<b>{order.currency} {order.grand_total:,.2f}</b>", right),
                    ]
                ],
                colWidths=[40 * mm, 55 * mm],
                hAlign="RIGHT",
                style=[("LINEABOVE", (0, 0), (-1, -1), 0.7, colors.black)],
            ),
            Spacer(1, 9 * mm),
        ]
    )

    def qr(payload: str | None) -> Any:
        if not payload:
            return Paragraph("Pending approval", center)
        image_stream = BytesIO()
        qrcode.make(payload).save(image_stream, format="PNG")
        image_stream.seek(0)
        return Image(image_stream, width=25 * mm, height=25 * mm)

    story.append(
        Table(
            [
                [Paragraph("<b>Created By</b>", center), Paragraph("<b>Approved By</b>", center)],
                [qr(order.creator_qr_payload), qr(order.approval_qr_payload)],
                [Paragraph(order.created_by_name, center), Paragraph(order.reviewed_by_name or "-", center)],
            ],
            colWidths=[65 * mm, 65 * mm],
            hAlign="CENTER",
            style=[("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")],
        )
    )
    document.build(story)
    return stream.getvalue()


def delivery_note_pdf_bytes(delivery: Any) -> bytes:
    """Render a delivery note with the same A4 visual language as PO/SO."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

    stream = BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"Delivery Note {delivery.delivery_number}",
    )
    styles = getSampleStyleSheet()
    center = ParagraphStyle("delivery-center", parent=styles["Normal"], alignment=TA_CENTER)
    story = [
        Paragraph("<b>SURAT JALAN</b>", styles["Title"]),
        Paragraph(f"<b>{delivery.delivery_number}</b>", center),
        Spacer(1, 5 * mm),
        Table(
            [
                [
                    "Delivery Date",
                    delivery.delivery_date.strftime("%d/%m/%Y"),
                    "Sales Order",
                    delivery.sales_order_number,
                ],
                ["Customer", delivery.customer_name, "Ship To", delivery.ship_to_name],
                [
                    "Address",
                    Paragraph(delivery.ship_to_address, styles["BodyText"]),
                    "Contact",
                    delivery.ship_to_contact,
                ],
                ["Vehicle", delivery.vehicle_number or "-", "Transportation", delivery.transportation_name or "-"],
                ["Driver", delivery.driver_name or "-", "Status", delivery.status_label],
            ],
            colWidths=[28 * mm, 55 * mm, 35 * mm, 60 * mm],
            style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.3, colors.grey)],
        ),
        Spacer(1, 5 * mm),
    ]
    rows = [["No", "Product", "Description", "Lot", "Qty", "Unit"]]
    for index, line in enumerate(delivery.lines, start=1):
        rows.append(
            [
                index,
                line.product_code,
                Paragraph(line.description or "-", styles["BodyText"]),
                line.lot_number,
                f"{line.quantity:,.3f}",
                "grams" if line.unit == "gram" else line.unit,
            ]
        )
    story.append(
        Table(
            rows,
            repeatRows=1,
            colWidths=[10 * mm, 27 * mm, 65 * mm, 27 * mm, 24 * mm, 17 * mm],
            style=[
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F659F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
            ],
        )
    )
    if delivery.notes:
        story.extend([Spacer(1, 4 * mm), Paragraph(f"<b>Notes:</b> {delivery.notes}", styles["BodyText"])])
    story.extend(
        [
            Spacer(1, 10 * mm),
            Table(
                [
                    [
                        Paragraph("<b>Prepared By</b>", center),
                        Paragraph("<b>Driver</b>", center),
                        Paragraph("<b>Received By</b>", center),
                    ],
                    ["\n\n\n\n", "\n\n\n\n", "\n\n\n\n"],
                    [
                        Paragraph(delivery.prepared_by_name, center),
                        Paragraph(delivery.driver_name or "-", center),
                        Paragraph("Name / Signature / Date", center),
                    ],
                ],
                colWidths=[55 * mm, 55 * mm, 55 * mm],
                hAlign="CENTER",
                style=[("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")],
            ),
        ]
    )
    document.build(story)
    return stream.getvalue()
