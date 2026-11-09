from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.document_services import invoice_pdf_bytes
from app.invoice_services import (
    format_invoice_number,
    invoice_amount_in_words,
    invoice_line_amount,
    invoice_quantity_available,
    invoice_totals,
)
from app.middleware import is_invoice_path
from app.schemas import InvoiceCreate


def test_invoice_amount_and_tax_are_calculated_from_sales_prices() -> None:
    amount_a = invoice_line_amount(Decimal("3"), Decimal("100.125"))
    amount_b = invoice_line_amount(Decimal("2"), Decimal("50"))
    assert amount_a == Decimal("300.38")
    assert amount_b == Decimal("100.00")

    subtotal, tax, total = invoice_totals([amount_a, amount_b], Decimal("50"), Decimal("11"))
    assert subtotal == Decimal("400.38")
    assert tax == Decimal("38.54")
    assert total == Decimal("388.92")


def test_invoice_discount_cannot_exceed_subtotal() -> None:
    with pytest.raises(ValueError, match="Discount cannot exceed"):
        invoice_totals([Decimal("100")], Decimal("100.01"), Decimal("11"))


def test_invoice_available_quantity_never_goes_negative() -> None:
    assert invoice_quantity_available(Decimal("10"), Decimal("4")) == Decimal("6")
    assert invoice_quantity_available(Decimal("10"), Decimal("12")) == Decimal("0")


def test_invoice_amount_is_spelled_in_english() -> None:
    whole_amount = invoice_amount_in_words(Decimal("222.00"))
    assert whole_amount == "Two hundred twenty-two rupiah only"
    assert "00/100" not in whole_amount
    assert invoice_amount_in_words(Decimal("30517063.50")) == (
        "Thirty million five hundred seventeen thousand sixty-three rupiah only"
    )
    assert invoice_amount_in_words(Decimal("1234.56"), "USD") == "One thousand two hundred thirty-four US dollars only"


def test_invoice_number_and_middleware_path_matching() -> None:
    assert format_invoice_number(date(2026, 11, 2), 7) == "INV-261102-007"
    assert is_invoice_path("/api/v1/invoices")
    assert is_invoice_path("/api/v1/invoices/INV-261102-007/pdf")
    assert not is_invoice_path("/api/v1/invoices-report")


def test_invoice_rejects_duplicate_source_line_and_due_date_before_issue_date() -> None:
    base = {
        "invoice_date": date(2026, 11, 2),
        "sales_order_number": "SO-261102-001",
        "items": [
            {
                "delivery_number": "DL-261102-001",
                "delivery_line_id": 5,
                "sales_order_item_id": 9,
                "quantity": Decimal("2"),
            }
        ],
    }
    duplicate = {**base, "items": base["items"] * 2}
    with pytest.raises(ValidationError, match="only be included once"):
        InvoiceCreate(**duplicate)

    invalid_due = {**base, "due_date": date(2026, 11, 1)}
    with pytest.raises(ValidationError, match="Due date"):
        InvoiceCreate(**invalid_due)


def test_invoice_pdf_uses_shared_pdf_document_layout() -> None:
    from types import SimpleNamespace

    invoice = SimpleNamespace(
        invoice_number="INV-261102-001",
        invoice_date=date(2026, 11, 2),
        sales_order_number="SO-261102-001",
        due_date=date(2026, 11, 30),
        customer_name="Customer",
        customer_address="Long customer address that should wrap inside its table cell",
        customer_contact_person="Contact",
        customer_phone="08123456789",
        status="issued",
        payment_terms="30 days",
        currency="IDR",
        items=[
            SimpleNamespace(
                line_number=1,
                delivery_number="DLV-261102-001",
                sales_order_number="SO-261102-001",
                part_name="Product",
                description="Description",
                lot_number="LOT-1",
                quantity=Decimal("2"),
                unit="pcs",
                unit_price=Decimal("100.0000"),
                amount=Decimal("200.00"),
            )
        ],
        subtotal=Decimal("200.00"),
        discount_amount=Decimal("0.00"),
        tax_label="PPN",
        tax_rate=Decimal("11.000"),
        tax_amount=Decimal("22.00"),
        grand_total=Decimal("222.00"),
        notes="Invoice note",
        void_reason=None,
        created_by="130826001",
        created_by_name="Sales User",
        created_at=datetime(2026, 11, 2, 10, 30),
    )
    pdf = invoice_pdf_bytes(invoice, customer_po_number="CPO-2026-001")
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000
