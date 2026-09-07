import re

import pytest
from pydantic import ValidationError

from app.master_data_services import build_initials, format_sequential_code, random_plant_code
from app.qr_services import parse_product_qr
from app.schemas import CorporationCreate, MachineCreate, ProductCreate, ProductResponse


def test_initials_and_sequential_codes_are_deterministic() -> None:
    assert build_initials("PT Astra Motor Indonesia") == "PAMI"
    assert build_initials("Brake Pad") == "BP"
    assert format_sequential_code("BP", 0) == "BP"
    assert format_sequential_code("BP", 1) == "BP001"
    assert format_sequential_code("BP", 999) == "BP999"


def test_sequential_code_rejects_out_of_range_sequence() -> None:
    with pytest.raises(ValueError):
        format_sequential_code("BP", 1000)


def test_random_plant_code_is_five_uppercase_alphanumeric_characters() -> None:
    codes = {random_plant_code() for _ in range(20)}
    assert all(re.fullmatch(r"[A-Z0-9]{5}", code) for code in codes)
    assert len(codes) > 1


def test_product_description_defaults_to_part_name_and_number() -> None:
    product = ProductCreate(
        customer_code="ACME",
        supplier_code="SUP",
        part_name="Brake Pad",
        part_no="BP-001",
        gross_weight=1.5,
        nett_weight=1.2,
    )
    assert product.description == "Brake Pad BP-001"


def test_product_rejects_negative_weight() -> None:
    with pytest.raises(ValidationError):
        ProductCreate(
            customer_code="ACME",
            supplier_code="SUP",
            part_name="Brake Pad",
            part_no="BP-001",
            gross_weight=-1,
            nett_weight=1,
        )


def test_internal_product_does_not_require_an_external_supplier() -> None:
    product = ProductCreate(
        customer_code="ACME",
        supply_source="manufactured_internally",
        part_name="Internal Assembly",
        part_no="IA-001",
        gross_weight=1,
        nett_weight=1,
    )
    assert product.supplier_code is None


def test_external_product_requires_a_supplier() -> None:
    with pytest.raises(ValidationError, match="Supplier is required"):
        ProductCreate(
            customer_code="ACME",
            part_name="External Part",
            part_no="EP-001",
            gross_weight=1,
            nett_weight=1,
        )


def test_product_response_exposes_current_stock_in_grams() -> None:
    assert ProductResponse.model_fields["current_stock_grams"].is_required()


def test_product_qr_parser_accepts_compact_and_structured_payloads() -> None:
    assert parse_product_qr("PJA") == ("PJA", None)
    assert parse_product_qr("MANUFLOW|PJA|LOT-01") == ("PJA", "LOT-01")
    assert parse_product_qr('{"product_code":"PJA","lot_number":"LOT-01"}') == ("PJA", "LOT-01")


def test_corporation_requires_customer_or_supplier_type() -> None:
    with pytest.raises(ValidationError):
        CorporationCreate(
            name="PT Example",
            address="Jakarta",
            phone_number="0211234",
            contact_person_name="Andi",
            contact_person_phone="0812345678",
            npwp="1234567890123456",
        )


def test_machine_rejects_unreasonable_year() -> None:
    with pytest.raises(ValidationError):
        MachineCreate(
            name="Press Machine",
            specification="100 ton",
            machine_type="Press",
            year=1700,
            country_of_origin="Japan",
            plant_code="A1B2C",
        )
