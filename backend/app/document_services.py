from datetime import datetime
from decimal import Decimal
from html import escape
from io import BytesIO
from typing import Any

import jwt
from openpyxl import Workbook

from app.config import settings


_DISCRETE_UNITS = {"pcs", "bar", "pail"}


def format_document_quantity(value: Any, unit: str | None) -> str:
    """Format quantities consistently with the application UI."""
    numeric = Decimal(str(value))
    if unit in _DISCRETE_UNITS:
        return f"{numeric:,.0f}"
    return f"{numeric:,.3f}".rstrip("0").rstrip(".")


def _pdf_styles(styles: Any) -> tuple[Any, Any, Any, Any]:
    """Shared, wrapping-safe cell styles for every printable document."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle

    cell = ParagraphStyle("document-cell", parent=styles["BodyText"], fontSize=8, leading=10, wordWrap="CJK")
    label = ParagraphStyle("document-label", parent=cell, fontName="Helvetica-Bold")
    header = ParagraphStyle("document-header", parent=cell, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_LEFT)
    right = ParagraphStyle("document-right", parent=cell, alignment=TA_RIGHT)
    return cell, label, header, right


def _pdf_text(value: Any, style: Any) -> Any:
    """Make every external value wrap inside its table cell and escape markup."""
    from reportlab.platypus import Paragraph

    if hasattr(value, "wrap"):
        return value
    text = "-" if value is None or str(value).strip() == "" else str(value)
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def _pdf_table(
    document: Any,
    rows: list[list[Any]],
    widths: list[float],
    cell_style: Any,
    *,
    header_style: Any | None = None,
    label_style: Any | None = None,
    metadata: bool = False,
    numeric_columns: tuple[int, ...] = (),
    repeat_rows: int = 0,
) -> Any:
    """A table that always fits printable width and wraps long content safely."""
    from reportlab.lib import colors
    from reportlab.platypus import Table

    scale = document.width / sum(widths)
    fitted_widths = [width * scale for width in widths]
    converted: list[list[Any]] = []
    for row_index, row in enumerate(rows):
        converted_row = []
        for column_index, value in enumerate(row):
            style = header_style if row_index == 0 and header_style is not None else cell_style
            if metadata and row_index >= (1 if header_style is not None else 0) and column_index % 2 == 0 and label_style is not None:
                style = label_style
            converted_row.append(_pdf_text(value, style))
        converted.append(converted_row)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header_style is not None:
        style.extend([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F659F")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)])
    for column in numeric_columns:
        style.append(("ALIGN", (column, 1 if header_style is not None else 0), (column, -1), "RIGHT"))
    return Table(converted, repeatRows=repeat_rows, colWidths=fitted_widths, style=style, splitByRow=1)


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
    cell, label, header, _ = _pdf_styles(styles)
    center = ParagraphStyle("center", parent=styles["Normal"], alignment=TA_CENTER)
    right = ParagraphStyle("right", parent=styles["Normal"], alignment=TA_RIGHT)
    story = [
        Paragraph("<b>PURCHASE ORDER</b>", styles["Title"]),
        Paragraph(f"<b>{order.po_number}</b>", center),
        Spacer(1, 5 * mm),
        _pdf_table(document, [
                ["PO Date", order.po_date.strftime("%d/%m/%Y"), "Supplier", order.supplier_name],
                [
                    "Plant",
                    order.delivery_plant_name,
                    "Requested Delivery",
                    order.requested_delivery_date.strftime("%d/%m/%Y"),
                ],
                ["Address", order.delivery_address, "Quotation", order.quotation_reference or "-"],
            ], [28 * mm, 55 * mm, 35 * mm, 60 * mm], cell, label_style=label, metadata=True),
        Spacer(1, 5 * mm),
    ]
    item_rows = [["No", "Product", "Description", "Qty", "Unit", "Price", "Amount"]]
    for item in order.items:
        item_rows.append(
            [
                item.line_number,
                item.product_code,
                item.description,
                format_document_quantity(item.quantity_grams, item.unit),
                "grams" if item.unit == "gram" else item.unit,
                f"{item.unit_price:,.2f}",
                f"{item.amount:,.2f}",
            ]
        )
    story.append(
        _pdf_table(document, item_rows, [9 * mm, 22 * mm, 58 * mm, 20 * mm, 17 * mm, 27 * mm, 29 * mm], cell, header_style=header, numeric_columns=(3, 5, 6), repeat_rows=1)
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
        [
            Paragraph("<b>Supplier</b>", center),
            Paragraph("<b>Created By</b>", center),
            Paragraph("<b>Approved By</b>", center),
        ],
        ["", qr_image(order.creator_qr_payload), qr_image(order.approval_qr_payload)],
        [
            Paragraph("Signature & Company Stamp", center),
            Paragraph(order.created_by_name, center),
            Paragraph(order.reviewed_by_name or "-", center),
        ],
    ]
    story.append(
        Table(
            signature_rows,
            colWidths=[60 * mm, 60 * mm, 60 * mm],
            rowHeights=[6 * mm, 30 * mm, 6 * mm],
            hAlign="CENTER",
            style=[
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEABOVE", (0, 2), (0, 2), 0.7, colors.black),
            ],
        )
    )
    document.build(story)
    return stream.getvalue()


def quotation_pdf_bytes(quotation: Any) -> bytes:
    """Render a standalone customer price quotation."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

    stream = BytesIO()
    document = SimpleDocTemplate(stream, pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm, title=f"Quotation {quotation.quotation_number}")
    styles = getSampleStyleSheet()
    cell, label, header, _ = _pdf_styles(styles)
    center = ParagraphStyle("quotation-center", parent=styles["Normal"], alignment=TA_CENTER)
    right = ParagraphStyle("quotation-right", parent=styles["Normal"], alignment=TA_RIGHT)
    story = [
        Paragraph("<b>QUOTATION</b>", styles["Title"]),
        Paragraph(f"<b>{quotation.quotation_number}</b>", center),
        Spacer(1, 5 * mm),
        _pdf_table(document, [["Quotation Date", quotation.quotation_date.strftime("%d/%m/%Y"), "Valid Until", quotation.valid_until.strftime("%d/%m/%Y")], ["Customer", quotation.customer_name, "Contact", quotation.customer_contact_person or "-"], ["Address", quotation.customer_address, "Phone", quotation.customer_phone or "-"]], [30 * mm, 62 * mm, 30 * mm, 62 * mm], cell, label_style=label, metadata=True),
        Spacer(1, 5 * mm),
    ]
    rows = [["No", "Product", "Description", "Qty", "Unit", "Price", "Amount"]]
    for item in quotation.items:
        rows.append([item.line_number, item.part_name, item.description, format_document_quantity(item.quantity, item.unit), "grams" if item.unit == "gram" else item.unit, f"{item.unit_price:,.2f}", f"{item.amount:,.2f}"])
    story.append(_pdf_table(document, rows, [9 * mm, 28 * mm, 53 * mm, 19 * mm, 16 * mm, 28 * mm, 28 * mm], cell, header_style=header, numeric_columns=(3, 5, 6), repeat_rows=1))
    story.extend([Spacer(1, 4 * mm), Table([["Subtotal", f"{quotation.currency} {quotation.subtotal:,.2f}"], ["Discount", f"{quotation.currency} {quotation.discount_amount:,.2f}"], [f"{quotation.tax_label} ({quotation.tax_rate}%)", f"{quotation.currency} {quotation.tax_amount:,.2f}"], ["Grand Total", f"{quotation.currency} {quotation.grand_total:,.2f}"]], colWidths=[125 * mm, 48 * mm], style=[("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")])])
    if quotation.payment_terms:
        story.extend([Spacer(1, 4 * mm), Paragraph("<b>Payment Terms</b>", styles["Heading4"]), Paragraph(quotation.payment_terms.replace("\n", "<br/>"), styles["BodyText"])])
    if quotation.notes:
        story.extend([Spacer(1, 3 * mm), Paragraph("<b>Notes</b>", styles["Heading4"]), Paragraph(quotation.notes.replace("\n", "<br/>"), styles["BodyText"])])
    story.extend([Spacer(1, 12 * mm), Paragraph(f"Prepared by: {quotation.created_by_name}", right)])
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
    cell, label, header, _ = _pdf_styles(styles)
    center = ParagraphStyle("pr-center", parent=styles["Normal"], alignment=TA_CENTER)
    story = [Paragraph("<b>PURCHASE REQUEST</b>", styles["Title"]), Paragraph(f"<b>{request.request_number}</b>", center), Spacer(1, 5 * mm)]
    status_value = getattr(request.status, "value", request.status)
    status_label = str(status_value).replace("_", " ").title()
    decision_label = "Rejected By" if status_value == "rejected" else "Approved By"
    metadata = [
        ["Date", request.request_date.strftime("%d/%m/%Y"), "Status", status_label],
        ["Requested By", request.created_by_name, "Department", request.department_code or "-"],
        ["Receiving Plant", request.delivery_plant_code or "-", "Expected Arrival", request.requested_delivery_date.strftime("%d/%m/%Y") if request.requested_delivery_date else "-"],
        ["Notes", request.notes or "-", decision_label, request.reviewed_by_name or "Pending review"],
        ["Reviewed At", request.reviewed_at.strftime("%d/%m/%Y %H:%M") if request.reviewed_at else "-", "", ""],
    ]
    story.append(_pdf_table(document, metadata, [28 * mm, 55 * mm, 35 * mm, 60 * mm], cell, label_style=label, metadata=True))
    rows = [["No", "Product", "Description", "Requested", "Approved", "Status", "Review Reason", "PO"]]
    for item in request.items:
        requested = f"{format_document_quantity(item.quantity, item.unit)} {item.unit}"
        approved = "-" if item.approved_quantity is None else f"{format_document_quantity(item.approved_quantity, item.unit)} {item.unit}"
        item_status = getattr(item.approval_status, "value", item.approval_status)
        rows.append([item.line_number, item.product_code, item.description, requested, approved, str(item_status).replace("_", " ").title(), item.review_reason or "-", item.purchase_order_number or "-"])
    story.extend([Spacer(1, 5 * mm), _pdf_table(document, rows, [8 * mm, 21 * mm, 40 * mm, 19 * mm, 19 * mm, 20 * mm, 31 * mm, 24 * mm], cell, header_style=header, repeat_rows=1)])
    def qr(payload: str | None):
        if not payload: return Paragraph("Pending review", center)
        image = BytesIO(); qrcode.make(payload).save(image, format="PNG"); image.seek(0)
        return Image(image, width=25 * mm, height=25 * mm)
    story.extend([Spacer(1, 9 * mm), Table([[Paragraph("<b>Submitted By</b>", center), Paragraph(f"<b>{decision_label}</b>", center)], [qr(request.creator_qr_payload), qr(request.review_qr_payload)], [Paragraph(request.created_by_name, center), Paragraph(request.reviewed_by_name or "-", center)]], colWidths=[65 * mm, 65 * mm], hAlign="CENTER", style=[("ALIGN", (0, 0), (-1, -1), "CENTER")])])
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
    cell, label, header, _ = _pdf_styles(styles)
    center = ParagraphStyle("so-center", parent=styles["Normal"], alignment=TA_CENTER)
    right = ParagraphStyle("so-right", parent=styles["Normal"], alignment=TA_RIGHT)
    story = [
        Paragraph("<b>SALES ORDER</b>", styles["Title"]),
        Paragraph(f"<b>{order.sales_order_number}</b>", center),
        Spacer(1, 5 * mm),
        _pdf_table(document, [
                ["PO Receipt", order.po_receipt_date.strftime("%d/%m/%Y"), "Customer", order.customer_name],
                ["Customer PO", order.customer_po_number, "Delivery", order.delivery_date.strftime("%d/%m/%Y")],
                ["Ship To", order.ship_to_name, "Address", order.ship_to_address],
            ], [28 * mm, 55 * mm, 35 * mm, 60 * mm], cell, label_style=label, metadata=True),
        Spacer(1, 5 * mm),
    ]
    rows = [["No", "Product", "Description", "Qty", "Unit", "Price", "Amount"]]
    for item in order.items:
        rows.append(
            [
                item.line_number,
                item.product_code,
                item.description,
                format_document_quantity(item.quantity_grams, item.unit),
                "grams" if item.unit == "gram" else item.unit,
                f"{item.unit_price:,.2f}",
                f"{item.amount:,.2f}",
            ]
        )
    story.append(
        _pdf_table(document, rows, [9 * mm, 22 * mm, 58 * mm, 20 * mm, 17 * mm, 27 * mm, 29 * mm], cell, header_style=header, numeric_columns=(3, 5, 6), repeat_rows=1)
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
    cell, label, header, _ = _pdf_styles(styles)
    center = ParagraphStyle("delivery-center", parent=styles["Normal"], alignment=TA_CENTER)
    story = [
        Paragraph("<b>DELIVERY NOTE</b>", styles["Title"]),
        Paragraph(f"<b>{delivery.delivery_number}</b>", center),
        Spacer(1, 5 * mm),
        _pdf_table(document, [
                [
                    "Delivery Date",
                    delivery.delivery_date.strftime("%d/%m/%Y"),
                    "Sales Order",
                    delivery.sales_order_number,
                ],
                ["Customer", delivery.customer_name, "Ship To", delivery.ship_to_name],
                [
                    "Address",
                    delivery.ship_to_address,
                    "Contact",
                    delivery.ship_to_contact,
                ],
                ["Vehicle", delivery.vehicle_number or "-", "Transportation", delivery.transportation_name or "-"],
                ["Driver", delivery.driver_name or "-", "Status", delivery.status_label],
            ], [28 * mm, 55 * mm, 35 * mm, 60 * mm], cell, label_style=label, metadata=True),
        Spacer(1, 5 * mm),
    ]
    rows = [["No", "Product", "Description", "Lot", "Qty", "Unit"]]
    for index, line in enumerate(delivery.lines, start=1):
        rows.append(
            [
                index,
                line.product_code,
                line.description or "-",
                line.lot_number,
                format_document_quantity(line.quantity, line.unit),
                "grams" if line.unit == "gram" else line.unit,
            ]
        )
    story.append(
        _pdf_table(document, rows, [10 * mm, 27 * mm, 65 * mm, 27 * mm, 24 * mm, 17 * mm], cell, header_style=header, numeric_columns=(4,), repeat_rows=1)
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
