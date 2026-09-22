from decimal import Decimal

from app.routers.analytics import product_stock_report_rows, stock_report_rows


def test_stock_report_rows_include_names_and_descriptions_for_code_references() -> None:
    records = stock_report_rows(
        [
            (
                "PRD-01",
                "Part A",
                "Part A Description",
                "LOT-001",
                "PLT-01",
                "Plant One",
                "LOC-01",
                "Main Rack",
                "Raw material storage",
                "pcs",
                Decimal("12"),
            )
        ]
    )

    assert records == [
        {
            "product_code": "PRD-01",
            "product_name": "Part A",
            "product_description": "Part A Description",
            "lot_number": "LOT-001",
            "plant_code": "PLT-01",
            "plant_name": "Plant One",
            "storage_location_code": "LOC-01",
            "storage_location_name": "Main Rack",
            "storage_location_description": "Raw material storage",
            "unit": "pcs",
            "quantity": Decimal("12"),
        }
    ]


def test_product_stock_summary_keeps_units_separate_and_includes_zero_stock_products() -> None:
    records = product_stock_report_rows(
        [
            (
                "PRD-01",
                "Part A",
                "A-001",
                "Part A Description",
                "raw_material",
                "external_supplier",
                "pcs",
                2,
                Decimal("12"),
            ),
            (
                "PRD-02",
                "Part B",
                "B-001",
                "Part B Description",
                "finished_good",
                "manufactured_internally",
                None,
                0,
                Decimal("0"),
            ),
        ]
    )

    assert records[0]["unit"] == "pcs"
    assert records[0]["stock_on_hand"] == Decimal("12")
    assert records[1]["unit"] == "-"
    assert records[1]["active_lot_count"] == 0
    assert records[1]["stock_on_hand"] == Decimal("0")
